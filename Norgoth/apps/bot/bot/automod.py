"""Rule-based auto-moderation: prohibited words, spam, invites, mass mentions,
image-only and link-only channels.

No AI involved — every rule is an explicit, dashboard-configured check.
Requires the Message Content intent.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from bot.automod_content import is_image_only_compliant, is_link_only_compliant
from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.automod")

INVITE_PATTERN = re.compile(
    r"(discord\.gg|discord(?:app)?\.com/invite)/[A-Za-z0-9-]+",
    re.IGNORECASE,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "moderation_scope": {"text": True, "threads": True, "voice_text": True},
    "words_enabled": True,
    "prohibited_words": [],
    "word_action": "delete",
    "spam_enabled": True,
    "spam_max_messages": 6,
    "spam_interval_seconds": 8,
    "spam_action": "timeout",
    "duplicate_enabled": True,
    "duplicate_threshold": 3,
    "block_invites": False,
    "invite_action": "delete",
    "mass_mention_enabled": True,
    "mass_mention_threshold": 6,
    "mass_mention_action": "delete",
    "timeout_minutes": 10,
    "exempt_manage_messages": True,
    "exempt_channel_ids": [],
    "exempt_role_ids": [],
    "image_only_enabled": False,
    "image_only_channel_ids": [],
    "image_only_action": "delete",
    "link_only_enabled": False,
    "link_only_channel_ids": [],
    "link_only_action": "delete",
}

FORMAT_RULES = frozenset({"image only channel", "link only channel"})
SEEN_TTL_SECONDS = 60
WARN_COOLDOWN_SECONDS = 30


def automod_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:automod"


def compile_word_patterns(words: list[str]) -> list[re.Pattern[str]]:
    patterns = []

    for word in words:
        cleaned = str(word).strip().lower()

        if not cleaned:
            continue

        if "*" in cleaned:
            regex = re.escape(cleaned).replace(r"\*", r"\S*")
        else:
            regex = rf"\b{re.escape(cleaned)}\b"

        try:
            patterns.append(re.compile(regex, re.IGNORECASE))
        except re.error:
            logger.warning("Skipping invalid prohibited word pattern: %s", word)

    return patterns


class AutoModCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        self._pattern_cache: dict[int, tuple[tuple[str, ...], list[re.Pattern[str]]]] = {}

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(automod_key(guild_id))
        if not stored:
            hydrated = await self.bot.state._hydrate_feature_from_api(
                guild_id, "automod"
            )
            if hydrated:
                await self.bot.state.set_json(automod_key(guild_id), hydrated)
                stored = hydrated
        return {**DEFAULT_CONFIG, **(stored or {})}

    def get_patterns(self, guild_id: int, words: list[str]) -> list[re.Pattern[str]]:
        cache_key = tuple(words)
        cached = self._pattern_cache.get(guild_id)

        if cached and cached[0] == cache_key:
            return cached[1]

        patterns = compile_word_patterns(words)
        self._pattern_cache[guild_id] = (cache_key, patterns)
        return patterns

    def _scope_for_channel(
        self, channel: Any
    ) -> tuple[str, int]:
        """Resolve a channel to its moderation scope + exemption channel id.

        - Threads resolve to their parent channel id so a parent-channel
          exemption (or scope toggle) also covers the thread.
        - Voice/stage text chat resolves to the voice channel id itself.
        - Everything else is treated as a normal text channel.
        """

        if isinstance(channel, discord.Thread):
            return "threads", (channel.parent_id or channel.id)
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return "voice_text", channel.id
        return "text", channel.id

    def _apply_channel_id(self, message: discord.Message) -> str:
        _scope, apply_id = self._scope_for_channel(message.channel)
        return str(apply_id)

    def _channel_ids_for_message(self, message: discord.Message) -> set[str]:
        ids = {str(message.channel.id)}
        parent_id = getattr(message.channel, "parent_id", None)
        if parent_id:
            ids.add(str(parent_id))
        ids.add(self._apply_channel_id(message))
        return ids

    async def _claim_violation(
        self,
        message: discord.Message,
        rule: str,
    ) -> bool:
        """Return True if this instance should apply the action."""

        guild = message.guild
        if guild is None:
            return False
        edited = getattr(message, "edited_at", None)
        stamp = int(edited.timestamp()) if edited else 0
        key = f"norgoth:guild:{guild.id}:automod:seen:{message.id}:{stamp}:{rule}"
        try:
            claimed = await self.bot.state.redis.set(
                key, "1", nx=True, ex=SEEN_TTL_SECONDS
            )
            return bool(claimed)
        except Exception:  # noqa: BLE001
            logger.debug("Automod seen-claim unavailable", exc_info=True)
            return True

    def is_exempt(self, message: discord.Message, config: dict[str, Any]) -> bool:
        member = message.author

        if not isinstance(member, discord.Member):
            return True

        if member.guild_permissions.manage_messages and config.get(
            "exempt_manage_messages", True
        ):
            return True

        # Exemptions match the channel itself AND (for threads) its parent, so a
        # parent-channel exemption transparently covers its threads.
        exempt_channels = set(config.get("exempt_channel_ids") or [])
        if exempt_channels & self._channel_ids_for_message(message):
            return True

        exempt_roles = set(config.get("exempt_role_ids") or [])

        if exempt_roles and any(str(role.id) in exempt_roles for role in member.roles):
            return True

        return False

    async def check_spam(
        self,
        message: discord.Message,
        config: dict[str, Any],
    ) -> str | None:
        """Returns the triggered rule name, or None."""

        guild_id = message.guild.id  # type: ignore[union-attr]
        user_id = message.author.id
        redis = self.bot.state.redis

        if config.get("spam_enabled"):
            interval = max(int(config.get("spam_interval_seconds") or 8), 1)
            limit = max(int(config.get("spam_max_messages") or 6), 2)

            rate_key = f"norgoth:guild:{guild_id}:automod:rate:{user_id}"
            count = await redis.incr(rate_key)

            if count == 1:
                await redis.expire(rate_key, interval)

            if count > limit:
                cooldown_key = f"norgoth:guild:{guild_id}:automod:cooldown:{user_id}"

                if await redis.set(cooldown_key, "1", nx=True, ex=interval * 2):
                    return "spam (message rate)"
                return "spam (message rate, repeat)"

        if config.get("duplicate_enabled") and message.content:
            threshold = max(int(config.get("duplicate_threshold") or 3), 2)
            dup_key = f"norgoth:guild:{guild_id}:automod:dup:{user_id}"

            previous = await redis.hgetall(dup_key)
            content = message.content.strip().lower()

            if previous.get("content") == content:
                count = int(previous.get("count") or 1) + 1
            else:
                count = 1

            await redis.hset(dup_key, mapping={"content": content, "count": count})
            await redis.expire(dup_key, 60)

            if count >= threshold:
                await redis.delete(dup_key)
                return "spam (repeated content)"

        return None

    async def apply_action(
        self,
        message: discord.Message,
        rule: str,
        action: str,
        config: dict[str, Any],
    ) -> None:
        member = message.author
        detail_parts = [f"rule: {rule}", f"action: {action}"]
        missing_manage_messages = False

        try:
            await message.delete()
        except discord.NotFound:
            detail_parts.append("already deleted")
        except discord.Forbidden:
            missing_manage_messages = True
            detail_parts.append("delete failed (missing permission)")
            logger.warning(
                "Automod missing Manage Messages for message %s in guild %s",
                message.id,
                message.guild.id if message.guild else "?",
            )
        except discord.HTTPException:
            logger.warning(
                "Automod could not delete message %s in guild %s",
                message.id,
                message.guild.id if message.guild else "?",
            )
            detail_parts.append("delete failed (Discord error)")

        if action in ("warn", "timeout") and not missing_manage_messages:
            warned = await self._send_warning(message, member, rule)
            if warned:
                detail_parts.append(f"warned in #{getattr(message.channel, 'name', '?')}")

        if action == "timeout" and isinstance(member, discord.Member):
            minutes = max(int(config.get("timeout_minutes") or 10), 1)

            try:
                await member.timeout(
                    timedelta(minutes=minutes),
                    reason=f"Norgoth automod: {rule}",
                )
                detail_parts.append(f"timeout {minutes}m")
            except discord.Forbidden:
                detail_parts.append("timeout failed (missing permission)")
            except discord.HTTPException:
                detail_parts.append("timeout failed (Discord error)")

        await self.log_automod_action(message, rule, ", ".join(detail_parts))

    async def _send_warning(
        self,
        message: discord.Message,
        member: discord.abc.User,
        rule: str,
    ) -> bool:
        guild = message.guild
        if guild is None:
            return False
        cooldown_key = (
            f"norgoth:guild:{guild.id}:automod:warn:"
            f"{message.channel.id}:{member.id}:{rule}"
        )
        try:
            acquired = await self.bot.state.redis.set(
                cooldown_key, "1", nx=True, ex=WARN_COOLDOWN_SECONDS
            )
            if not acquired:
                return False
        except Exception:  # noqa: BLE001
            logger.debug("Automod warn cooldown unavailable", exc_info=True)

        mentions = discord.AllowedMentions(
            everyone=False,
            roles=False,
            users=[member],
        )
        try:
            await message.channel.send(
                f"{member.mention} your message was removed by "
                f"auto-moderation ({rule}).",
                allowed_mentions=mentions,
                delete_after=8,
            )
            return True
        except discord.HTTPException:
            return False

    async def log_automod_action(
        self,
        message: discord.Message,
        rule: str,
        detail: str,
    ) -> None:
        guild = message.guild

        if guild is None:
            return

        entry = {
            "action": f"automod:{rule}",
            "moderator_id": str(self.bot.user.id) if self.bot.user else "bot",
            "moderator_name": "Norgoth AutoMod",
            "target": f"{message.author} ({message.author.id})",
            "reason": rule,
            "detail": detail,
            "created_at": now_iso(),
        }

        try:
            await self.bot.state.append_moderation_log(guild.id, entry)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist automod log entry")

        # Route into central config-driven logging (Security event group).
        logging_cog = self.bot.get_cog("ServerLoggingCog")
        if logging_cog is not None:
            try:
                await logging_cog.record_event(
                    guild,
                    "security",
                    "Auto-moderation action",
                    f"Auto-moderation acted on {message.author} for {rule}.",
                    {
                        "Member": f"{message.author} ({message.author.id})",
                        "Channel": getattr(message.channel, "mention", "?"),
                        "Rule": rule,
                        "Detail": detail[:1024],
                    },
                    event_type="automod_action",
                    actor_id=str(message.author.id),
                    actor_name=str(message.author),
                )
            except Exception:  # noqa: BLE001 - logging must never break automod
                logger.exception("Failed to route automod event to central logging")

        config = await self.bot.state.get_automation_config(guild.id)
        log_channel_id = config.get("mod_log_channel_id")

        if not log_channel_id:
            return

        channel = guild.get_channel(int(log_channel_id))

        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title="Auto-Moderation",
            description=f"Rule triggered: **{rule}**",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Member",
            value=f"{message.author.mention} ({message.author.id})",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=getattr(message.channel, "mention", "?"),
            inline=True,
        )
        embed.add_field(name="Detail", value=detail[:1024], inline=False)

        if message.content and rule not in FORMAT_RULES:
            embed.add_field(
                name="Message",
                value=message.content[:512],
                inline=False,
            )

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.exception("Failed to post automod embed")

    async def evaluate_message(
        self,
        message: discord.Message,
        config: dict[str, Any],
    ) -> tuple[str, str] | None:
        """Run every enabled rule against a message.

        Returns the first triggered ``(rule, action)`` pair, or ``None``. This is
        the single moderation engine shared across text channels, threads, and
        voice-channel side chat — scope resolution happens before this is called.
        """

        content = message.content or ""
        apply_ids = self._channel_ids_for_message(message)

        if config.get("image_only_enabled"):
            image_channels = {
                str(channel_id)
                for channel_id in (config.get("image_only_channel_ids") or [])
            }
            if apply_ids & image_channels and not is_image_only_compliant(message):
                return "image only channel", str(
                    config.get("image_only_action") or "delete"
                )

        if config.get("link_only_enabled"):
            link_channels = {
                str(channel_id)
                for channel_id in (config.get("link_only_channel_ids") or [])
            }
            if apply_ids & link_channels and not is_link_only_compliant(message):
                return "link only channel", str(
                    config.get("link_only_action") or "delete"
                )

        # Prohibited words
        words = config.get("prohibited_words") or []
        if config.get("words_enabled", True) and words:
            patterns = self.get_patterns(
                message.guild.id,  # type: ignore[union-attr]
                [str(w) for w in words],
            )
            for pattern in patterns:
                if pattern.search(content):
                    return "prohibited word", str(
                        config.get("word_action") or "delete"
                    )

        # Invite links
        if config.get("block_invites") and INVITE_PATTERN.search(content):
            return "invite link", str(config.get("invite_action") or "delete")

        # Mass mentions
        if config.get("mass_mention_enabled"):
            threshold = max(int(config.get("mass_mention_threshold") or 6), 2)
            mention_count = len(message.mentions) + len(message.role_mentions)
            if message.mention_everyone or mention_count >= threshold:
                return "mass mentions", str(
                    config.get("mass_mention_action") or "delete"
                )

        # Spam (rate + repeated content)
        spam_rule = await self.check_spam(message, config)
        if spam_rule:
            return spam_rule, str(config.get("spam_action") or "timeout")

        return None

    async def _process_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return

        if not await self.bot.state.is_module_enabled(message.guild.id, "automod"):
            return

        config = await self.get_config(message.guild.id)

        if not config.get("enabled"):
            return

        # Honor the configured moderation scope (text / threads / voice text).
        scope_key, _ = self._scope_for_channel(message.channel)
        scope = config.get("moderation_scope") or {}
        if not scope.get(scope_key, True):
            return

        if self.is_exempt(message, config):
            return

        try:
            result = await self.evaluate_message(message, config)
        except Exception:  # noqa: BLE001 - Redis/regex hiccups must not kill the listener
            logger.exception("Automod evaluation failed")
            return

        if result is None:
            return

        rule, action = result
        if not await self._claim_violation(message, rule):
            return
        await self.apply_action(message, rule, action, config)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._process_message(message)

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        _before: discord.Message,
        after: discord.Message,
    ) -> None:
        await self._process_message(after)

    @commands.Cog.listener()
    async def on_raw_message_edit(
        self,
        payload: discord.RawMessageUpdateEvent,
    ) -> None:
        if payload.cached_message is not None:
            return
        data = payload.data or {}
        if "content" not in data and "attachments" not in data:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.HTTPException:
                return
        if not isinstance(
            channel,
            (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel),
        ):
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        except discord.Forbidden:
            logger.warning(
                "Automod could not fetch edited message %s in channel %s",
                payload.message_id,
                payload.channel_id,
            )
            return
        except discord.HTTPException:
            return
        await self._process_message(message)
