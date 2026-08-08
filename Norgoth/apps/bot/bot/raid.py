"""Raid protection: join-rate / young-account detection and auto responses."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands, tasks

from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.raid")

JOINS_KEY_TTL = 300
INCIDENTS_CAP = 100

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "alert_channel_id": None,
    "joins_per_minute": 10,
    "young_account_age_days": 7,
    "young_account_ratio": 50,
    "response_duration_minutes": 30,
    "respond_automatically": False,
    "pause_invites": False,
    "force_verification": False,
    "kick_young_accounts": False,
    "pause_invite_crediting": False,
}


def raid_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:raid"


def raid_joins_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:raid:joins"


def raid_incidents_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:raid:incidents"


def raid_incident_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:raid:incident"


def pause_invite_credit_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:raid:pause_invite_credit"


def account_age_days(member: discord.Member) -> float:
    created = member.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0.0, (discord.utils.utcnow() - created).total_seconds() / 86400.0)


class RaidCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        self.incident_watch.start()

    def cog_unload(self) -> None:
        self.incident_watch.cancel()

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(raid_key(guild_id))
        return {**DEFAULT_CONFIG, **stored}

    async def get_active_incident(self, guild_id: int) -> dict[str, Any] | None:
        raw = await self.bot.state.redis.get(raid_incident_key(guild_id))
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    async def record_join(
        self,
        member: discord.Member,
        *,
        invite_code: str | None,
        inviter_id: str | None,
    ) -> dict[str, Any]:
        age = account_age_days(member)
        now = time.time()
        entry = {
            "user_id": str(member.id),
            "user_name": str(member),
            "created_at": member.created_at.isoformat(),
            "age_days": round(age, 2),
            "invite": invite_code,
            "inviter_id": inviter_id,
            "joined_at": now_iso(),
            "ts": now,
        }

        redis = self.bot.state.redis
        key = raid_joins_key(member.guild.id)
        await redis.zadd(key, {json.dumps(entry): now})
        await redis.zremrangebyscore(key, 0, now - 120)
        await redis.expire(key, JOINS_KEY_TTL)
        return entry

    async def recent_joins(self, guild_id: int, window_seconds: float = 60.0) -> list[dict[str, Any]]:
        redis = self.bot.state.redis
        now = time.time()
        raw_members = await redis.zrangebyscore(
            raid_joins_key(guild_id),
            now - window_seconds,
            now,
        )

        joins: list[dict[str, Any]] = []
        for raw in raw_members:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                joins.append(parsed)
        return joins

    async def maybe_end_incident(self, guild: discord.Guild) -> None:
        incident = await self.get_active_incident(guild.id)
        if not incident:
            return

        ends_at = incident.get("ends_at")
        if not ends_at:
            return

        try:
            end_time = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return

        if discord.utils.utcnow() < end_time:
            return

        await self.end_incident(guild, incident)

    async def end_incident(self, guild: discord.Guild, incident: dict[str, Any]) -> None:
        redis = self.bot.state.redis
        actions_taken = list(incident.get("actions_taken") or [])
        restore_notes: list[str] = []

        me = guild.me
        can_manage = bool(me and me.guild_permissions.manage_guild)

        if can_manage and incident.get("paused_invites"):
            try:
                await guild.edit(
                    invites_disabled=False,
                    reason="Norgoth raid protection: incident ended",
                )
                restore_notes.append("invites re-enabled")
            except (discord.Forbidden, discord.HTTPException):
                restore_notes.append("failed to re-enable invites")

        previous_level = incident.get("previous_verification_level")
        if can_manage and previous_level is not None:
            try:
                level = discord.VerificationLevel(int(previous_level))
                await guild.edit(
                    verification_level=level,
                    reason="Norgoth raid protection: restore verification",
                )
                restore_notes.append(f"verification restored to {level.name}")
            except (ValueError, discord.Forbidden, discord.HTTPException):
                restore_notes.append("failed to restore verification level")

        incident["status"] = "ended"
        incident["ended_at"] = now_iso()
        incident["restore_notes"] = restore_notes
        if restore_notes:
            actions_taken.extend(restore_notes)
            incident["actions_taken"] = actions_taken

        await redis.delete(raid_incident_key(guild.id))
        await redis.delete(pause_invite_credit_key(guild.id))

        # Update the head of the incidents list if it matches.
        try:
            head = await redis.lindex(raid_incidents_key(guild.id), 0)
            if head:
                parsed = json.loads(head)
                if isinstance(parsed, dict) and parsed.get("id") == incident.get("id"):
                    await redis.lset(
                        raid_incidents_key(guild.id),
                        0,
                        json.dumps(incident),
                    )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to update ended raid incident in list")

        await self.send_alert(
            guild,
            incident,
            title="Raid Protection — Incident Ended",
            color=discord.Color.green(),
            extra_lines=restore_notes,
        )
        logger.info("Raid incident ended in guild %s", guild.id)

    async def start_incident(
        self,
        guild: discord.Guild,
        config: dict[str, Any],
        joins: list[dict[str, Any]],
        joining_member: discord.Member,
    ) -> dict[str, Any]:
        duration = max(int(config.get("response_duration_minutes") or 30), 1)
        young_age = max(int(config.get("young_account_age_days") or 7), 1)
        young_count = sum(
            1 for join in joins if float(join.get("age_days") or 0) < young_age
        )
        ratio = int(round((young_count / len(joins)) * 100)) if joins else 0

        started = discord.utils.utcnow()
        ends = started.timestamp() + (duration * 60)

        incident: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "status": "active",
            "started_at": started.isoformat(),
            "ends_at": datetime.fromtimestamp(ends, tz=timezone.utc).isoformat(),
            "joins_per_minute": len(joins),
            "young_account_ratio": ratio,
            "young_account_age_days": young_age,
            "trigger_member_id": str(joining_member.id),
            "trigger_member_name": str(joining_member),
            "alert_channel_id": config.get("alert_channel_id"),
            "actions_taken": [],
            "paused_invites": False,
            "previous_verification_level": None,
            "join_sample": joins[-20:],
        }

        redis = self.bot.state.redis
        await redis.set(raid_incident_key(guild.id), json.dumps(incident))
        await redis.lpush(raid_incidents_key(guild.id), json.dumps(incident))
        await redis.ltrim(raid_incidents_key(guild.id), 0, INCIDENTS_CAP - 1)

        await self.send_alert(
            guild,
            incident,
            title="Raid Protection — Incident Detected",
            color=discord.Color.red(),
        )

        # Route into central config-driven logging (Security event group) in
        # addition to the dedicated alert channel above.
        logging_cog = self.bot.get_cog("ServerLoggingCog")
        if logging_cog is not None:
            try:
                await logging_cog.record_event(
                    guild,
                    "security",
                    "Raid detected",
                    "Raid protection detected a rapid join burst.",
                    {
                        "Joins/min": str(incident.get("joins_per_minute", "?")),
                        "Young accounts": f"{incident.get('young_account_ratio', '?')}%",
                        "Trigger member": incident.get("trigger_member_name", "?"),
                    },
                    event_type="raid_detected",
                    actor_id=incident.get("trigger_member_id"),
                    actor_name=incident.get("trigger_member_name"),
                )
            except Exception:  # noqa: BLE001 - logging must never break raid response
                logger.exception("Failed to route raid event to central logging")

        if config.get("respond_automatically"):
            await self.apply_auto_responses(
                guild,
                config,
                incident,
                joining_member,
                duration_minutes=duration,
            )

        return incident

    async def apply_auto_responses(
        self,
        guild: discord.Guild,
        config: dict[str, Any],
        incident: dict[str, Any],
        member: discord.Member,
        *,
        duration_minutes: int,
    ) -> None:
        actions: list[str] = list(incident.get("actions_taken") or [])
        me = guild.me
        can_manage = bool(me and me.guild_permissions.manage_guild)
        redis = self.bot.state.redis

        if config.get("pause_invite_crediting"):
            await redis.set(
                pause_invite_credit_key(guild.id),
                "1",
                ex=duration_minutes * 60,
            )
            actions.append("paused invite crediting")

        if config.get("pause_invites") and can_manage:
            try:
                await guild.edit(
                    invites_disabled=True,
                    reason="Norgoth raid protection: pause invites",
                )
                incident["paused_invites"] = True
                actions.append("paused invites")
            except (discord.Forbidden, discord.HTTPException) as error:
                actions.append(f"pause invites failed: {error}")

        if config.get("force_verification") and can_manage:
            try:
                incident["previous_verification_level"] = int(guild.verification_level.value)
                await guild.edit(
                    verification_level=discord.VerificationLevel.high,
                    reason="Norgoth raid protection: force verification",
                )
                actions.append("forced high verification")
            except (discord.Forbidden, discord.HTTPException) as error:
                actions.append(f"force verification failed: {error}")

        if config.get("kick_young_accounts"):
            young_age = max(int(config.get("young_account_age_days") or 7), 1)
            if account_age_days(member) < young_age:
                try:
                    await member.kick(reason="Norgoth raid protection: young account")
                    actions.append(f"kicked young account {member.id}")
                except (discord.Forbidden, discord.HTTPException) as error:
                    actions.append(f"kick young account failed: {error}")

        incident["actions_taken"] = actions
        await redis.set(raid_incident_key(guild.id), json.dumps(incident))

        try:
            head = await redis.lindex(raid_incidents_key(guild.id), 0)
            if head:
                parsed = json.loads(head)
                if isinstance(parsed, dict) and parsed.get("id") == incident.get("id"):
                    await redis.lset(
                        raid_incidents_key(guild.id),
                        0,
                        json.dumps(incident),
                    )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist raid auto-response actions")

    async def send_alert(
        self,
        guild: discord.Guild,
        incident: dict[str, Any],
        *,
        title: str,
        color: discord.Color,
        extra_lines: list[str] | None = None,
    ) -> None:
        channel_id = incident.get("alert_channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Joins / minute",
            value=str(incident.get("joins_per_minute", "?")),
            inline=True,
        )
        embed.add_field(
            name="Young account ratio",
            value=f"{incident.get('young_account_ratio', '?')}%",
            inline=True,
        )
        embed.add_field(
            name="Status",
            value=str(incident.get("status") or "?"),
            inline=True,
        )

        actions = incident.get("actions_taken") or []
        if actions:
            embed.add_field(
                name="Actions",
                value="\n".join(f"• {action}" for action in actions)[:1024],
                inline=False,
            )

        if extra_lines:
            embed.add_field(
                name="Notes",
                value="\n".join(f"• {line}" for line in extra_lines)[:1024],
                inline=False,
            )

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.exception("Failed to send raid alert in guild %s", guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        guild = member.guild

        if not await self.bot.state.is_module_enabled(guild.id, "raid"):
            return

        config = await self.get_config(guild.id)
        if not config.get("enabled"):
            return

        try:
            await self.maybe_end_incident(guild)
        except Exception:  # noqa: BLE001
            logger.exception("Raid incident end-check failed in guild %s", guild.id)

        invite_code: str | None = None
        inviter_id: str | None = None

        try:
            invites_cog = self.bot.get_cog("InvitesCog")
            if invites_cog is not None and await self.bot.state.is_module_enabled(
                guild.id, "invites"
            ):
                # Idempotent with InvitesCog.on_member_join; respects pause-credit flag.
                inviter_id, invite_code = await invites_cog.attribute_join(member)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            logger.exception("Raid invite attribution failed for %s", member)

        try:
            await self.record_join(
                member,
                invite_code=invite_code,
                inviter_id=inviter_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to record raid join in guild %s", guild.id)
            return

        active = await self.get_active_incident(guild.id)
        if active:
            # During an active incident, still kick young accounts if configured.
            if (
                config.get("respond_automatically")
                and config.get("kick_young_accounts")
            ):
                young_age = max(int(config.get("young_account_age_days") or 7), 1)
                if account_age_days(member) < young_age:
                    try:
                        await member.kick(
                            reason="Norgoth raid protection: young account (active incident)"
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            return

        joins = await self.recent_joins(guild.id, 60.0)
        joins_threshold = max(int(config.get("joins_per_minute") or 10), 2)
        young_age = max(int(config.get("young_account_age_days") or 7), 1)
        young_ratio_threshold = int(config.get("young_account_ratio") or 50)

        if len(joins) < joins_threshold:
            return

        young_count = sum(
            1 for join in joins if float(join.get("age_days") or 0) < young_age
        )
        ratio = int(round((young_count / len(joins)) * 100)) if joins else 0

        # Trigger when join flood is met AND young-account ratio is high enough
        # (ratio threshold 0 means join rate alone is enough).
        if young_ratio_threshold > 0 and ratio < young_ratio_threshold:
            return

        try:
            await self.start_incident(guild, config, joins, member)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to start raid incident in guild %s", guild.id)

    @tasks.loop(seconds=30)
    async def incident_watch(self) -> None:
        for guild in self.bot.guilds:
            try:
                await self.maybe_end_incident(guild)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Raid incident watch failed for guild %s", guild.id
                )

    @incident_watch.before_loop
    async def before_incident_watch(self) -> None:
        await self.bot.wait_until_ready()
