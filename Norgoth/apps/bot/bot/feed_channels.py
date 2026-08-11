"""Feed Channels: seed vote reactions, track messages, sync canonical votes."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import discord
import httpx
from discord.ext import commands, tasks

from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.feed")

API_TIMEOUT = 15.0
REPAIR_TIMEOUT = 280.0
_VOTE_SUPPRESS_TTL_SEC = 5.0
# Discord GIF picker + direct media URLs (Klipy/Tenor/Giphy page or CDN).
_CONTENT_MEDIA_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:media\.)?tenor\.com/[^\s<>\"]+"
    r"|https?://(?:media\d*\.)?giphy\.com/[^\s<>\"]+"
    r"|https?://(?:www\.)?giphy\.com/[^\s<>\"]+"
    r"|https?://(?:www\.)?klipy\.com/[^\s<>\"]+"
    r"|https?://static\.klipy\.com/[^\s<>\"]+"
    r"|https?://(?:i\.)?imgur\.com/[^\s<>\"]+"
    r"|https?://[^\s<>\"]+\.(?:png|jpe?g|gif|webp|gifv)(?:\?[^\s<>\"]*)?",
    re.IGNORECASE,
)
_VIDEO_ONLY_SUFFIXES = (".mp4", ".webm", ".mov")
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".gifv")


def _truncate_media(url: str | None) -> str | None:
    if not url:
        return None
    return str(url)[:1024]


def _usable_embed_image_url(url: str | None) -> str | None:
    """Return URL only if Discord embed ``image.url`` can render it.

    Rejects mp4/webm (gifv video) and bare GIF-picker page links
    (``klipy.com/gifs/...``, ``tenor.com/view/...``) which show as text only.
    """

    cleaned = _truncate_media(url)
    if not cleaned:
        return None
    path = cleaned.lower().split("?", 1)[0]
    if path.endswith(_VIDEO_ONLY_SUFFIXES):
        return None
    lower = cleaned.lower()
    if "klipy.com/gifs/" in lower and "static.klipy.com" not in lower:
        return None
    if "tenor.com/view/" in lower:
        return None
    if re.search(r"https?://(?:www\.)?giphy\.com/gifs/", lower):
        return None
    return cleaned


def _emoji_match(payload_emoji: discord.PartialEmoji, configured: dict[str, Any] | None) -> bool:
    if not configured:
        return False
    if configured.get("kind") == "custom" and configured.get("id"):
        return str(payload_emoji.id or "") == str(configured["id"])
    # Unicode
    return str(payload_emoji) == str(configured.get("reaction") or configured.get("name") or "")


def _reaction_str(configured: dict[str, Any] | None) -> str | None:
    if not configured:
        return None
    if configured.get("reaction"):
        return str(configured["reaction"])
    if configured.get("kind") == "custom" and configured.get("id"):
        name = configured.get("name") or "emoji"
        return f"a:{name}:{configured['id']}" if configured.get("animated") else f"{name}:{configured['id']}"
    return str(configured.get("name") or "") or None


def _author_snapshot(message: discord.Message) -> tuple[str | None, str | None]:
    """Return (display_name, avatar_url) for feed embed author block."""

    author = message.author
    name = None
    if isinstance(author, discord.Member):
        name = author.display_name or author.global_name or author.name
    else:
        name = getattr(author, "global_name", None) or getattr(author, "name", None)
    display = str(name)[:128] if name else None
    avatar_url = None
    try:
        avatar = author.display_avatar
        if avatar is not None and getattr(avatar, "url", None):
            avatar_url = str(avatar.url)[:1024]
    except Exception:  # noqa: BLE001
        avatar_url = None
    return display, avatar_url


def _primary_media_url(message: discord.Message) -> str | None:
    """Pick primary image/GIF URL for feed embed image field.

    Priority: image/GIF attachment → embed image → embed thumbnail →
    embed video (only if image-like) → direct media URL in content.

    Discord GIF picker (Klipy/Tenor/Giphy) posts are usually ``gifv`` embeds:
    video=mp4 + thumbnail=webp. Bot embeds only support ``image``, so prefer
    the thumbnail over the mp4.
    """

    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        name = (attachment.filename or "").lower()
        if content_type.startswith("image/") or name.endswith(_IMAGE_EXTENSIONS):
            url = _usable_embed_image_url(attachment.proxy_url or attachment.url)
            if url:
                logger.info(
                    "Feed media selected source=attachment message=%s",
                    message.id,
                )
                return url

    for embed in message.embeds:
        if embed.image and embed.image.url:
            url = _usable_embed_image_url(embed.image.url)
            if url:
                logger.info(
                    "Feed media selected source=embed_image message=%s",
                    message.id,
                )
                return url

    for embed in message.embeds:
        if embed.thumbnail and embed.thumbnail.url:
            thumb_proxy = getattr(embed.thumbnail, "proxy_url", None)
            url = _usable_embed_image_url(thumb_proxy or embed.thumbnail.url)
            if url:
                logger.info(
                    "Feed media selected source=embed_thumbnail message=%s",
                    message.id,
                )
                return url

    for embed in message.embeds:
        video = getattr(embed, "video", None)
        if video is not None:
            video_url = getattr(video, "proxy_url", None) or getattr(video, "url", None)
            url = _usable_embed_image_url(video_url)
            if url:
                logger.info(
                    "Feed media selected source=embed_video message=%s",
                    message.id,
                )
                return url

    content = message.content or ""
    # Strip Discord <> URL suppression wrappers for matching.
    content_unwrapped = content.replace("<", "").replace(">", "")
    match = _CONTENT_MEDIA_URL_RE.search(content_unwrapped)
    if match:
        # Prefer embeddable CDN URLs; page links are kept only as a hint so
        # rebuild refresh can resolve Discord's gifv thumbnail later.
        raw = _truncate_media(match.group(0))
        usable = _usable_embed_image_url(raw)
        if usable:
            logger.info(
                "Feed media selected source=content_url message=%s",
                message.id,
            )
            return usable
        if raw:
            logger.info(
                "Feed media selected source=content_gif_page message=%s",
                message.id,
            )
            return raw
    return None


def _clamp_refresh_minutes(value: Any) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = 15
    minutes = max(5, min(60, minutes))
    snapped = round((minutes - 5) / 5) * 5 + 5
    return max(5, min(60, int(snapped)))


def _parse_iso_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _is_feed_refresh_due(config: dict[str, Any], *, now: datetime | None = None) -> bool:
    """Mirror API is_feed_refresh_due: prefer stored next_refresh_at."""

    if not config.get("enabled"):
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    next_at = _parse_iso_utc(config.get("next_refresh_at"))
    if next_at is not None:
        return current >= next_at
    last = _parse_iso_utc(config.get("last_full_sync_at"))
    if last is None:
        return True
    interval_min = _clamp_refresh_minutes(config.get("refresh_interval_minutes"))
    return current >= last + timedelta(minutes=interval_min)


class FeedChannelsCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        # Suppress bot-driven opposite-reaction removals so they do not clear votes.
        self._suppress_vote_removes: dict[str, float] = {}
        self._dirty_loop.start()
        self._refresh_loop.start()

    def cog_unload(self) -> None:
        self._dirty_loop.cancel()
        self._refresh_loop.cancel()

    def _suppress_key(
        self,
        guild_id: int,
        message_id: int,
        user_id: int,
        emoji_key: str,
    ) -> str:
        return f"{guild_id}:{message_id}:{user_id}:{emoji_key}"

    def _emoji_suppress_key(self, payload_emoji: discord.PartialEmoji) -> str:
        if payload_emoji.id:
            return f"id:{payload_emoji.id}"
        return f"u:{payload_emoji}"

    def _configured_emoji_suppress_key(self, configured: dict[str, Any] | None) -> str | None:
        if not configured:
            return None
        if configured.get("kind") == "custom" and configured.get("id"):
            return f"id:{configured['id']}"
        reaction = configured.get("reaction") or configured.get("name")
        return f"u:{reaction}" if reaction else None

    def _mark_suppress_remove(
        self,
        guild_id: int,
        message_id: int,
        user_id: int,
        configured: dict[str, Any] | None,
    ) -> None:
        key_emoji = self._configured_emoji_suppress_key(configured)
        if not key_emoji:
            return
        key = self._suppress_key(guild_id, message_id, user_id, key_emoji)
        self._suppress_vote_removes[key] = time.monotonic() + _VOTE_SUPPRESS_TTL_SEC

    def _consume_suppress_remove(
        self,
        guild_id: int,
        message_id: int,
        user_id: int,
        payload_emoji: discord.PartialEmoji,
    ) -> bool:
        """Return True if this REMOVE should be ignored (bot exclusivity cleanup)."""

        now = time.monotonic()
        # Drop expired entries opportunistically.
        expired = [k for k, exp in self._suppress_vote_removes.items() if exp <= now]
        for k in expired:
            self._suppress_vote_removes.pop(k, None)

        key = self._suppress_key(
            guild_id, message_id, user_id, self._emoji_suppress_key(payload_emoji)
        )
        exp = self._suppress_vote_removes.pop(key, None)
        return exp is not None and exp > now

    async def _module_enabled(self, guild_id: int) -> bool:
        modules = await self.bot.state.get_json(f"norgoth:guild:{guild_id}:modules") or {}
        # Default enabled when key missing (matches modules route defaults).
        return bool(modules.get("feed_channels", True))

    async def _config(self, guild_id: int) -> dict[str, Any]:
        raw = await self.bot.state.get_json(f"norgoth:guild:{guild_id}:feed:config")
        if isinstance(raw, dict) and raw:
            return raw
        hydrated = await self.bot.state._hydrate_feature_from_api(
            guild_id, "feed_channels"
        )
        if isinstance(hydrated, dict) and hydrated:
            import json

            await self.bot.state.redis.set(
                f"norgoth:guild:{guild_id}:feed:config",
                json.dumps(hydrated),
            )
            return hydrated
        return {}

    async def _add_configured_reaction(
        self, message: discord.Message, configured: dict[str, Any] | None
    ) -> bool:
        reaction = _reaction_str(configured)
        if not reaction:
            return False
        try:
            if configured and configured.get("kind") == "custom" and configured.get("id"):
                emoji = discord.PartialEmoji(
                    name=str(configured.get("name") or "emoji"),
                    id=int(configured["id"]),
                    animated=bool(configured.get("animated")),
                )
                await message.add_reaction(emoji)
            else:
                await message.add_reaction(reaction)
            return True
        except (discord.HTTPException, ValueError, TypeError):
            logger.info("Could not add feed reaction on %s", message.id)
            return False

    def _feed_destination_ids(self, config: dict[str, Any]) -> set[str]:
        ids: set[str] = set()
        for window in (config.get("windows") or {}).values():
            if isinstance(window, dict) and window.get("channel_id"):
                ids.add(str(window["channel_id"]))
        return ids

    def _is_eligible_message(
        self,
        message: discord.Message,
        config: dict[str, Any],
    ) -> bool:
        if not config.get("enabled"):
            return False
        if config.get("exclude_bots", True) and message.author.bot:
            return False
        if config.get("exclude_webhooks", True) and message.webhook_id:
            return False
        if message.type not in (
            discord.MessageType.default,
            discord.MessageType.reply,
        ):
            return False
        if config.get("exclude_threads", True) and isinstance(
            message.channel, discord.Thread
        ):
            return False
        channel_id = str(message.channel.id)
        if channel_id in self._feed_destination_ids(config):
            return False
        sources = [str(x) for x in (config.get("source_channel_ids") or [])]
        excluded = [str(x) for x in (config.get("excluded_channel_ids") or [])]
        if channel_id in excluded:
            return False
        if not sources or channel_id not in sources:
            return False
        return True

    async def _ingest(self, guild_id: int, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        settings = self.bot.settings
        base = (settings.api_base_url or "").rstrip("/")
        token = settings.token
        if not base or not token:
            return None
        url = f"{base}/internal/ingest/{guild_id}/{path}"
        try:
            timeout = REPAIR_TIMEOUT if path == "feed-repair" else API_TIMEOUT
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    headers={"X-Norgoth-Bot-Token": token},
                    json=payload,
                )
            if response.status_code >= 400:
                logger.warning(
                    "Feed ingest %s failed: HTTP %s %s",
                    path,
                    response.status_code,
                    response.text[:200],
                )
                return None
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception:  # noqa: BLE001
            logger.exception("Feed ingest %s error", path)
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        if not await self._module_enabled(message.guild.id):
            return
        config = await self._config(message.guild.id)
        if not self._is_eligible_message(message, config):
            return

        up_ok = await self._add_configured_reaction(message, config.get("upvote_emoji"))
        down_ok = await self._add_configured_reaction(
            message, config.get("downvote_emoji")
        )
        if not up_ok and not down_ok:
            return

        excerpt = (message.content or "").strip()
        display_name, avatar_url = _author_snapshot(message)
        await self._ingest(
            message.guild.id,
            "feed-message",
            {
                "channel_id": str(message.channel.id),
                "message_id": str(message.id),
                "author_id": str(message.author.id),
                "created_at": (message.created_at or datetime.now(timezone.utc)).isoformat(),
                "content_excerpt": excerpt[:500] if excerpt else None,
                "attachment_count": len(message.attachments),
                "primary_media_url": _primary_media_url(message),
                "author_display_name": display_name,
                "author_avatar_url": avatar_url,
            },
        )

    async def _handle_reaction(
        self,
        payload: discord.RawReactionActionEvent,
        *,
        removed: bool,
    ) -> None:
        if payload.guild_id is None or self.bot.user is None:
            return
        if payload.user_id == self.bot.user.id:
            return
        if not await self._module_enabled(payload.guild_id):
            return
        config = await self._config(payload.guild_id)
        if not config.get("enabled"):
            return

        if removed and self._consume_suppress_remove(
            payload.guild_id,
            payload.message_id,
            payload.user_id,
            payload.emoji,
        ):
            logger.info(
                "Feed vote: suppressed exclusivity remove guild=%s message=%s user=%s",
                payload.guild_id,
                payload.message_id,
                payload.user_id,
            )
            return

        vote: str | None = None
        if _emoji_match(payload.emoji, config.get("upvote_emoji")):
            vote = None if removed else "up"
            vote_kind = "up"
        elif _emoji_match(payload.emoji, config.get("downvote_emoji")):
            vote = None if removed else "down"
            vote_kind = "down"
        else:
            return

        result = await self._ingest(
            payload.guild_id,
            "feed-vote",
            {
                "message_id": str(payload.message_id),
                "voter_id": str(payload.user_id),
                "vote": vote,
                "from_feed_entry": True,
            },
        )
        if not result or not result.get("changed"):
            return

        # Mutual exclusivity: remove the opposite reaction on the reacted message.
        previous = result.get("previous_vote") or result.get("previous")
        if (
            not removed
            and previous
            and previous != vote_kind
        ):
            opposite = (
                config.get("downvote_emoji")
                if vote_kind == "up"
                else config.get("upvote_emoji")
            )
            opposite_str = _reaction_str(opposite)
            channel = self.bot.get_channel(payload.channel_id)
            if opposite_str and isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(payload.message_id)
                    member = payload.member or channel.guild.get_member(payload.user_id)
                    if member is not None:
                        self._mark_suppress_remove(
                            payload.guild_id,
                            payload.message_id,
                            payload.user_id,
                            opposite,
                        )
                        logger.info(
                            "Feed vote: switch %s→%s guild=%s message=%s user=%s",
                            previous,
                            vote_kind,
                            payload.guild_id,
                            payload.message_id,
                            payload.user_id,
                        )
                        if ":" in opposite_str:
                            parts = opposite_str.split(":")
                            emoji = discord.PartialEmoji(
                                name=parts[-2],
                                id=int(parts[-1]),
                                animated=opposite_str.startswith("a:"),
                            )
                            await message.remove_reaction(emoji, member)
                        else:
                            await message.remove_reaction(opposite_str, member)
                except (discord.HTTPException, discord.Forbidden, ValueError):
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self._handle_reaction(payload, removed=False)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self._handle_reaction(payload, removed=True)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        if payload.guild_id is None:
            return
        if not await self._module_enabled(payload.guild_id):
            return
        await self._ingest(
            payload.guild_id,
            "feed-message-deleted",
            {"message_id": str(payload.message_id)},
        )

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: discord.Message,
        after: discord.Message,
    ) -> None:
        if after.guild is None:
            return
        if not await self._module_enabled(after.guild.id):
            return
        excerpt = (after.content or "").strip()
        display_name, avatar_url = _author_snapshot(after)
        await self._ingest(
            after.guild.id,
            "feed-message-edited",
            {
                "message_id": str(after.id),
                "content_excerpt": excerpt[:500] if excerpt else None,
                "attachment_count": len(after.attachments),
                "primary_media_url": _primary_media_url(after),
                "author_display_name": display_name,
                "author_avatar_url": avatar_url,
            },
        )

    @tasks.loop(seconds=60)
    async def _dirty_loop(self) -> None:
        for guild in list(self.bot.guilds):
            try:
                if not await self._module_enabled(guild.id):
                    continue
                config = await self._config(guild.id)
                if not config.get("enabled"):
                    continue
                await self._ingest(guild.id, "feed-process-dirty", {})
            except Exception:  # noqa: BLE001
                logger.exception("Feed dirty loop failed for guild %s", guild.id)

    @_dirty_loop.before_loop
    async def _before_dirty(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=1)
    async def _refresh_loop(self) -> None:
        """Full sync when guild next_refresh_at is due (guild-scoped)."""

        for guild in list(self.bot.guilds):
            try:
                if not await self._module_enabled(guild.id):
                    continue
                config = await self._config(guild.id)
                if not _is_feed_refresh_due(config):
                    continue
                result = await self._ingest(guild.id, "feed-repair", {})
                if result is not None:
                    logger.info(
                        "Feed auto refresh completed guild=%s next=%s status=%s",
                        guild.id,
                        result.get("next_refresh_at"),
                        result.get("scheduler_status"),
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Feed refresh loop failed for guild %s", guild.id)

    @_refresh_loop.before_loop
    async def _before_refresh(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "NorgothBot") -> None:
    await bot.add_cog(FeedChannelsCog(bot))
