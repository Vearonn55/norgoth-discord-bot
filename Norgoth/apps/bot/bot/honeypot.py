"""Honeypot trap channels: punish members who post where they shouldn't."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands, tasks

from bot.state import now_iso
from bot.embed_render import build_embed_from_json

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.honeypot")

TRIGGERS_CAP = 500

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "trap_channel_ids": [],
    "post_pinned_warning": True,
    "warning_content": (
        "⚠️ This channel is a honeypot trap. Do not post here. "
        "Posting will result in moderation action."
    ),
    "warning_embed": None,
    "punishment": "kick",
    "delete_history_hours": 0,
    "ignore_bots": True,
    "exempt_role_ids": [],
    "exempt_member_ids": [],
    "log_channel_id": None,
    "ping_role_id": None,
    "timeout_minutes": 60,
}


def honeypot_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:honeypot"


def honeypot_triggers_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:honeypot:triggers"


def honeypot_warning_lock_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:honeypot:warning-lock"


WARNING_LOCK_TTL_SECONDS = 120
WARNING_HISTORY_SCAN = 50


def missing_warning_permissions(perms: Any) -> list[str]:
    """Return Discord permission names required to post and pin a warning."""

    missing: list[str] = []
    if not getattr(perms, "view_channel", True):
        missing.append("view_channel")
    if not getattr(perms, "send_messages", False):
        missing.append("send_messages")
    if not getattr(perms, "read_message_history", True):
        missing.append("read_message_history")
    can_pin = bool(getattr(perms, "manage_messages", False)) or bool(
        getattr(perms, "pin_messages", False)
    )
    if not can_pin:
        missing.append("manage_messages")
    return missing


def warning_status_ok() -> dict[str, Any]:
    return {"ok": True}


def warning_status_error(
    code: str,
    message: str,
    *,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "code": code, "message": message}
    if missing:
        payload["missing"] = missing
    return payload


def is_duplicate_warning(
    message: Any,
    *,
    me_id: int,
    canonical_id: str | None,
    content: str | None,
    embed_title: str | None,
) -> bool:
    author = getattr(message, "author", None)
    if getattr(author, "id", None) != me_id:
        return False
    if canonical_id and str(getattr(message, "id", "")) == str(canonical_id):
        return False
    if bool(getattr(message, "pinned", False)):
        return True
    msg_content = str(getattr(message, "content", None) or "").strip() or None
    if content and msg_content == content:
        return True
    if embed_title:
        for embed in getattr(message, "embeds", None) or []:
            if getattr(embed, "title", None) == embed_title:
                return True
    return False


class HoneypotCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        self.maintenance_loop.start()

    def cog_unload(self) -> None:
        self.maintenance_loop.cancel()

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(honeypot_key(guild_id))
        if stored and not stored.get("warning_message_id"):
            hydrated = await self.bot.state._hydrate_feature_from_api(
                guild_id, "honeypot"
            )
            if hydrated and hydrated.get("warning_message_id"):
                stored = hydrated
                await self.bot.state.set_json(honeypot_key(guild_id), stored)
        if not stored:
            stored = await self.bot.state._hydrate_feature_from_api(
                guild_id, "honeypot"
            )
            if stored:
                await self.bot.state.set_json(honeypot_key(guild_id), stored)
        return {**DEFAULT_CONFIG, **(stored or {})}

    async def save_config(self, guild_id: int, config: dict[str, Any]) -> None:
        config["updated_at"] = now_iso()
        await self.bot.state.persist_feature_config(
            guild_id,
            "honeypot",
            config,
            enabled=bool(config.get("enabled")),
        )

    def is_exempt(self, member: discord.Member, config: dict[str, Any]) -> bool:
        if member.id == member.guild.owner_id:
            return True

        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            return True

        if str(member.id) in set(config.get("exempt_member_ids") or []):
            return True

        exempt_roles = set(config.get("exempt_role_ids") or [])
        if exempt_roles and any(str(role.id) in exempt_roles for role in member.roles):
            return True

        return False

    def build_warning_embed(self, config: dict[str, Any]) -> discord.Embed | None:
        raw = config.get("warning_embed")
        if not isinstance(raw, dict) or not raw:
            return None
        return build_embed_from_json(raw)

    async def ensure_pinned_warning(
        self,
        guild: discord.Guild,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        if not config.get("post_pinned_warning"):
            return config

        trap_ids = [
            str(cid)
            for cid in (config.get("trap_channel_ids") or [])
            if str(cid).isdigit()
        ]
        if not trap_ids:
            return config

        channel = guild.get_channel(int(trap_ids[0]))
        if not isinstance(channel, discord.TextChannel):
            return config

        me = guild.me
        if me is None:
            return config

        missing = missing_warning_permissions(channel.permissions_for(me))
        if missing:
            config["warning_status"] = warning_status_error(
                "missing_permissions",
                "NorBot is missing permissions to post or pin the honeypot warning.",
                missing=missing,
            )
            await self.save_config(guild.id, config)
            return config

        redis = self.bot.state.redis
        lock_key = honeypot_warning_lock_key(guild.id)
        acquired = await redis.set(
            lock_key,
            "1",
            nx=True,
            ex=WARNING_LOCK_TTL_SECONDS,
        )
        if not acquired:
            return config

        try:
            return await self._ensure_pinned_warning_locked(guild, channel, me, config)
        finally:
            try:
                await redis.delete(lock_key)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to release honeypot warning lock guild=%s", guild.id
                )

    async def _ensure_pinned_warning_locked(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        me: discord.Member,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        warning_message_id = config.get("warning_message_id")
        warning_channel_id = config.get("warning_channel_id")
        content = str(config.get("warning_content") or "").strip() or None
        embed = self.build_warning_embed(config)
        embed_title = None
        raw_embed = config.get("warning_embed")
        if isinstance(raw_embed, dict):
            embed_title = str(raw_embed.get("title") or "") or None

        if warning_channel_id and str(warning_channel_id) != str(channel.id):
            old_channel = guild.get_channel(int(warning_channel_id))
            if isinstance(old_channel, discord.TextChannel) and warning_message_id:
                try:
                    old_message = await old_channel.fetch_message(
                        int(warning_message_id)
                    )
                    if getattr(old_message.author, "id", None) == me.id:
                        if old_message.pinned:
                            await old_message.unpin(reason="Honeypot warning moved")
                        await old_message.delete()
                except (discord.NotFound, discord.HTTPException, ValueError):
                    pass
            warning_message_id = None
            config["warning_message_id"] = None
            config["warning_channel_id"] = None
            config["warning_pinned"] = False

        existing: discord.Message | None = None
        if warning_message_id:
            try:
                existing = await channel.fetch_message(int(warning_message_id))
            except discord.NotFound:
                existing = None
            except discord.HTTPException as error:
                status = int(getattr(error, "status", 0) or 0)
                if status == 404:
                    existing = None
                else:
                    code = (
                        "missing_permissions"
                        if status in {401, 403}
                        else "discord_unavailable"
                    )
                    config["warning_status"] = warning_status_error(
                        code,
                        "Could not verify the existing honeypot warning.",
                    )
                    await self.save_config(guild.id, config)
                    return config
            except ValueError:
                existing = None

        if existing is not None and existing.author.id == me.id:
            try:
                await existing.edit(content=content, embed=embed)
            except discord.HTTPException:
                logger.exception(
                    "Failed to edit honeypot warning in guild %s channel %s",
                    guild.id,
                    channel.id,
                )
                config["warning_status"] = warning_status_error(
                    "discord_unavailable",
                    "Could not update the existing honeypot warning.",
                )
                await self.save_config(guild.id, config)
                return config

            pinned = bool(existing.pinned)
            if not pinned:
                try:
                    await existing.pin(reason="Norgoth honeypot warning")
                    pinned = True
                except discord.HTTPException:
                    logger.exception(
                        "Failed to pin honeypot warning in guild %s channel %s",
                        guild.id,
                        channel.id,
                    )
                    config["warning_message_id"] = str(existing.id)
                    config["warning_channel_id"] = str(channel.id)
                    config["warning_pinned"] = False
                    config["force_warning_repost"] = False
                    config["warning_status"] = warning_status_error(
                        "pin_failed",
                        "The honeypot warning exists but could not be pinned.",
                    )
                    await self.save_config(guild.id, config)
                    return config
            config["warning_message_id"] = str(existing.id)
            config["warning_channel_id"] = str(channel.id)
            config["warning_pinned"] = True
            config["force_warning_repost"] = False
            config["warning_status"] = warning_status_ok()
            await self.save_config(guild.id, config)
            await self._cleanup_duplicate_warnings(
                channel,
                me_id=me.id,
                canonical_id=str(existing.id),
                content=content,
                embed_title=embed_title,
            )
            logger.info(
                "honeypot warning skip-if-exists guild=%s channel=%s",
                guild.id,
                channel.id,
            )
            return config

        try:
            message = await channel.send(content=content, embed=embed)
        except discord.HTTPException:
            logger.exception(
                "Failed to post honeypot warning in guild %s channel %s",
                guild.id,
                channel.id,
            )
            config["warning_status"] = warning_status_error(
                "discord_unavailable",
                "Could not post the honeypot warning.",
            )
            await self.save_config(guild.id, config)
            return config

        config["warning_message_id"] = str(message.id)
        config["warning_channel_id"] = str(channel.id)
        config["warning_posted_at"] = now_iso()
        config["warning_pinned"] = False
        config["force_warning_repost"] = False
        config["warning_status"] = warning_status_ok()
        await self.save_config(guild.id, config)

        try:
            await message.pin(reason="Norgoth honeypot warning")
        except discord.HTTPException:
            logger.exception(
                "Failed to pin honeypot warning in guild %s channel %s",
                guild.id,
                channel.id,
            )
            config["warning_pinned"] = False
            config["warning_status"] = warning_status_error(
                "pin_failed",
                "The honeypot warning was posted but could not be pinned.",
            )
            await self.save_config(guild.id, config)
            return config

        config["warning_pinned"] = True
        config["warning_status"] = warning_status_ok()
        await self.save_config(guild.id, config)
        await self._cleanup_duplicate_warnings(
            channel,
            me_id=me.id,
            canonical_id=str(message.id),
            content=content,
            embed_title=embed_title,
        )
        logger.info(
            "honeypot warning posted-once guild=%s channel=%s message=%s",
            guild.id,
            channel.id,
            message.id,
        )
        return config

    async def _cleanup_duplicate_warnings(
        self,
        channel: discord.TextChannel,
        *,
        me_id: int,
        canonical_id: str,
        content: str | None,
        embed_title: str | None,
    ) -> None:
        candidates: list[Any] = []
        seen: set[int] = set()
        try:
            pins = await channel.pins()
        except discord.HTTPException:
            pins = []
        for message in pins:
            message_id = int(getattr(message, "id", 0) or 0)
            if message_id and message_id not in seen:
                seen.add(message_id)
                candidates.append(message)
        try:
            async for message in channel.history(limit=WARNING_HISTORY_SCAN):
                message_id = int(getattr(message, "id", 0) or 0)
                if message_id and message_id not in seen:
                    seen.add(message_id)
                    candidates.append(message)
        except discord.HTTPException:
            pass

        for message in candidates:
            if not is_duplicate_warning(
                message,
                me_id=me_id,
                canonical_id=canonical_id,
                content=content,
                embed_title=embed_title,
            ):
                continue
            try:
                await message.delete()
            except discord.HTTPException:
                logger.exception(
                    "Failed to delete duplicate honeypot warning channel=%s message=%s",
                    channel.id,
                    getattr(message, "id", None),
                )

    async def apply_punishment(
        self,
        message: discord.Message,
        member: discord.Member,
        config: dict[str, Any],
    ) -> str:
        punishment = str(config.get("punishment") or "kick")
        details: list[str] = [f"punishment={punishment}"]

        if punishment != "log_only":
            try:
                await message.delete()
                details.append("message deleted")
            except discord.HTTPException:
                details.append("message delete failed")

        if punishment == "timeout":
            minutes = max(int(config.get("timeout_minutes") or 60), 1)
            try:
                await member.timeout(
                    timedelta(minutes=minutes),
                    reason="Norgoth honeypot",
                )
                details.append(f"timeout {minutes}m")
            except (discord.Forbidden, discord.HTTPException) as error:
                details.append(f"timeout failed: {error}")

        elif punishment == "kick":
            try:
                await member.kick(reason="Norgoth honeypot")
                details.append("kicked")
            except (discord.Forbidden, discord.HTTPException) as error:
                details.append(f"kick failed: {error}")

        elif punishment == "kick_purge":
            try:
                await member.kick(reason="Norgoth honeypot (purge)")
                details.append("kicked")
            except (discord.Forbidden, discord.HTTPException) as error:
                details.append(f"kick failed: {error}")

            # Best-effort purge of the member's recent messages in the trap channel.
            channel = message.channel
            if isinstance(channel, discord.TextChannel):
                try:
                    deleted = await channel.purge(
                        limit=100,
                        check=lambda msg: msg.author.id == member.id,
                        bulk=True,
                    )
                    details.append(f"purged {len(deleted)} messages")
                except (discord.Forbidden, discord.HTTPException):
                    details.append("purge failed")

        elif punishment == "ban":
            hours = max(0, min(int(config.get("delete_history_hours") or 0), 24))
            delete_seconds = hours * 3600
            try:
                await member.ban(
                    reason="Norgoth honeypot",
                    delete_message_seconds=delete_seconds,
                )
                details.append(f"banned (delete {hours}h history)")
            except (discord.Forbidden, discord.HTTPException) as error:
                details.append(f"ban failed: {error}")

        return "; ".join(details)

    async def record_trigger(
        self,
        message: discord.Message,
        member: discord.Member,
        *,
        punishment: str,
        result: str,
    ) -> dict[str, Any]:
        entry = {
            "id": str(uuid.uuid4()),
            "member_id": str(member.id),
            "member_name": str(member),
            "channel_id": str(message.channel.id),
            "channel_name": getattr(message.channel, "name", str(message.channel.id)),
            "message_id": str(message.id),
            "content_preview": (message.content or "")[:200],
            "punishment": punishment,
            "result": result,
            "created_at": now_iso(),
        }

        try:
            await self.bot.state.append_capped_list(
                honeypot_triggers_key(member.guild.id),
                entry,
                cap=TRIGGERS_CAP,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to append honeypot trigger")

        try:
            await self.bot.state.append_moderation_log(
                member.guild.id,
                {
                    "action": f"honeypot:{punishment}",
                    "moderator_id": str(self.bot.user.id) if self.bot.user else "bot",
                    "moderator_name": "Norgoth Honeypot",
                    "target": f"{member} ({member.id})",
                    "reason": "Posted in honeypot channel",
                    "detail": result,
                    "created_at": now_iso(),
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to append honeypot modlog entry")

        return entry

    async def route_to_central_logging(
        self,
        guild: discord.Guild,
        member: discord.Member,
        entry: dict[str, Any],
    ) -> None:
        """Route a honeypot trigger through the central logging cog.

        Honeypot no longer owns a dedicated log destination: triggers are a
        `security` group event (`honeypot_triggered`) routed by the guild's
        Logging Configuration. The moderation-log audit trail is kept separately
        in `record_trigger`.
        """

        logging_cog = self.bot.get_cog("ServerLoggingCog")
        if logging_cog is None:
            return

        fields = {
            "Member": f"{member} ({member.id})",
            "Channel": f"<#{entry['channel_id']}>",
            "Punishment": str(entry.get("punishment") or "?"),
            "Result": str(entry.get("result") or "")[:1024],
        }
        preview = entry.get("content_preview")
        if preview:
            fields["Message"] = str(preview)[:512]

        try:
            await logging_cog.record_event(
                guild,
                "security",
                "Honeypot member detected",
                f"{member} was detected in a honeypot trap.",
                {
                    "Member": f"{member} ({member.id})",
                    "Channel": f"<#{entry['channel_id']}>",
                },
                event_type="honeypot_member_detected",
                actor_id=str(member.id),
                actor_name=str(member),
            )
            await logging_cog.record_event(
                guild,
                "security",
                "Honeypot triggered",
                f"{member} posted in a honeypot trap channel.",
                fields,
                event_type="honeypot_triggered",
                actor_id=str(member.id),
                actor_name=str(member),
            )
            await logging_cog.record_event(
                guild,
                "security",
                "Honeypot punishment applied",
                f"Honeypot punishment applied to {member}.",
                {
                    "Member": f"{member} ({member.id})",
                    "Punishment": str(entry.get("punishment") or "?"),
                    "Result": str(entry.get("result") or "")[:1024],
                },
                event_type="honeypot_punishment_applied",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        except Exception:  # noqa: BLE001 - logging must never break honeypot
            logger.exception("Failed to route honeypot event to central logging")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        if not isinstance(message.author, discord.Member):
            return

        if not await self.bot.state.is_module_enabled(message.guild.id, "honeypot"):
            return

        config = await self.get_config(message.guild.id)
        if not config.get("enabled"):
            return

        trap_ids = {str(cid) for cid in (config.get("trap_channel_ids") or [])}
        if str(message.channel.id) not in trap_ids:
            return

        # Ignore the bot's own pinned warning message.
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        if config.get("ignore_bots", True) and message.author.bot:
            return

        if self.is_exempt(message.author, config):
            return

        # Don't punish someone for interacting with the warning pin itself
        # if they somehow own it; already covered by bot check.

        punishment = str(config.get("punishment") or "kick")

        try:
            result = await self.apply_punishment(message, message.author, config)
        except Exception:  # noqa: BLE001
            logger.exception("Honeypot punishment failed")
            result = "punishment crashed"

        entry = await self.record_trigger(
            message,
            message.author,
            punishment=punishment,
            result=result,
        )
        await self.route_to_central_logging(message.guild, message.author, entry)

    @tasks.loop(seconds=45)
    async def maintenance_loop(self) -> None:
        for guild in self.bot.guilds:
            try:
                if not await self.bot.state.is_module_enabled(guild.id, "honeypot"):
                    continue

                config = await self.get_config(guild.id)
                if config.get("enabled") and config.get("post_pinned_warning"):
                    await self.ensure_pinned_warning(guild, config)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Honeypot maintenance failed for guild %s", guild.id
                )

    @maintenance_loop.before_loop
    async def before_maintenance(self) -> None:
        await self.bot.wait_until_ready()
