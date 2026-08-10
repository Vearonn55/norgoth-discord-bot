"""Sync Top Trending rank messages via Discord REST (clean rebuild)."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.models.feed_channels import FeedEntry, FeedMessage
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import save_config
from app.services.feed_ranking import (
    DISPLAY_LIMIT_MAX,
    FEED_WINDOWS,
    FeedWindow,
    clamp_display_limit,
    composite_rank_score,
    emoji_reaction_key,
    feed_debounce_key,
    feed_dirty_key,
    feed_lock_key,
    feed_rank_key,
    load_merged_feed_config,
    merge_feed_config,
    window_bounds,
)

logger = logging.getLogger("norgoth.feed.rebuild")

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".gifv")
_VIDEO_ONLY_SUFFIXES = (".mp4", ".webm", ".mov")
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


def _usable_embed_image_url(url: str | None) -> str | None:
    """URL suitable for Discord message embed ``image.url`` (not gifv mp4)."""

    if not url:
        return None
    cleaned = str(url).strip()[:1024]
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


def primary_media_from_discord_payload(data: dict[str, Any]) -> str | None:
    """Extract a fresh image/GIF URL from a Discord message JSON payload.

    Prefer thumbnail over video for gifv (Klipy/Tenor) so bot embeds can use
    ``image.url`` (mp4 is not renderable there).
    """

    for attachment in data.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        content_type = str(attachment.get("content_type") or "").lower()
        name = str(attachment.get("filename") or "").lower()
        if content_type.startswith("image/") or name.endswith(_IMAGE_EXTENSIONS):
            url = _usable_embed_image_url(
                attachment.get("proxy_url") or attachment.get("url")
            )
            if url:
                return url

    for embed in data.get("embeds") or []:
        if not isinstance(embed, dict):
            continue
        image = embed.get("image")
        if isinstance(image, dict):
            url = _usable_embed_image_url(image.get("url"))
            if url:
                return url

    for embed in data.get("embeds") or []:
        if not isinstance(embed, dict):
            continue
        thumb = embed.get("thumbnail")
        if isinstance(thumb, dict):
            url = _usable_embed_image_url(
                thumb.get("proxy_url") or thumb.get("url")
            )
            if url:
                return url

    for embed in data.get("embeds") or []:
        if not isinstance(embed, dict):
            continue
        video = embed.get("video")
        if isinstance(video, dict):
            url = _usable_embed_image_url(
                video.get("proxy_url") or video.get("url")
            )
            if url:
                return url

    content = str(data.get("content") or "").replace("<", "").replace(">", "")
    match = _CONTENT_MEDIA_URL_RE.search(content)
    if match:
        raw = match.group(0)[:1024]
        return _usable_embed_image_url(raw) or raw
    return None


async def top_messages_for_window(
    session: AsyncSession,
    *,
    guild_id: str,
    window: FeedWindow,
    min_net_score: int,
    limit: int,
) -> list[FeedMessage]:
    start, end = window_bounds(window)
    filters = [
        FeedMessage.guild_id == guild_id,
        FeedMessage.status == "active",
        FeedMessage.net_score >= min_net_score,
    ]
    if start is not None and end is not None:
        filters.append(FeedMessage.created_at >= start)
        filters.append(FeedMessage.created_at < end)

    rows = (
        await session.execute(
            select(FeedMessage)
            .where(and_(*filters))
            .order_by(
                FeedMessage.net_score.desc(),
                FeedMessage.upvote_count.desc(),
                FeedMessage.created_at.desc(),
                FeedMessage.message_id.desc(),
            )
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


WINDOW_FOOTER_LABELS: dict[str, str] = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "all_time": "All Time",
}

# Discord embed description limit is 4096; leave room for jump link.
_DESCRIPTION_BODY_MAX = 3500


async def refresh_feed_message_media(
    bot: DiscordBotClient,
    message: FeedMessage,
) -> None:
    """Refresh primary_media_url from Discord (CDN URLs expire)."""

    try:
        raw = await bot.get_channel_message(message.channel_id, message.message_id)
    except DiscordBotAPIError as error:
        if error.status_code != 404:
            logger.debug(
                "Feed media refresh failed message=%s status=%s",
                message.message_id,
                error.status_code,
            )
        return
    if not isinstance(raw, dict):
        return
    url = primary_media_from_discord_payload(raw)
    if url:
        message.primary_media_url = url


def _strip_media_url_from_excerpt(excerpt: str, media_url: str = "") -> str:
    """Remove media URL(s) from text so Discord doesn't show a raw link."""

    if not excerpt:
        return excerpt
    text = excerpt
    if media_url:
        candidates = {media_url.strip()}
        base = media_url.split("?", 1)[0].strip()
        if base:
            candidates.add(base)
        for candidate in sorted(candidates, key=len, reverse=True):
            if candidate:
                text = text.replace(candidate, " ")
    # Drop GIF-picker / direct media URLs left in the caption.
    text = _CONTENT_MEDIA_URL_RE.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_feed_embed(
    *,
    rank: int,
    message: FeedMessage,
    upvote_emoji: str,
    downvote_emoji: str,
    window: FeedWindow | str = "daily",
) -> dict[str, Any]:
    """Build a Discord message payload for a ranked feed post (never empty)."""

    jump = (
        f"https://discord.com/channels/{message.guild_id}/"
        f"{message.channel_id}/{message.message_id}"
    )
    media = (message.primary_media_url or "").strip()
    normalized_media: str | None = None
    if media:
        try:
            from app.services.media.service import normalize_feed_media_url

            normalized_media = _usable_embed_image_url(
                normalize_feed_media_url(media) or media
            )
        except Exception:  # noqa: BLE001
            normalized_media = _usable_embed_image_url(media)
            logger.exception(
                "Feed embed: media normalize failed message=%s", message.message_id
            )

    excerpt = (message.content_excerpt or "").strip()
    if normalized_media:
        # Image will render; strip picker page links (klipy/tenor/giphy) and CDN URLs.
        excerpt = _strip_media_url_from_excerpt(excerpt, media)
        if normalized_media != media:
            excerpt = _strip_media_url_from_excerpt(excerpt, normalized_media)
    if not excerpt and not normalized_media:
        excerpt = "*No text content*"
    if len(excerpt) > _DESCRIPTION_BODY_MAX:
        excerpt = excerpt[: _DESCRIPTION_BODY_MAX - 1] + "…"

    from datetime import timezone

    created = message.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    ts = int(created.timestamp())

    description = f"{excerpt}\n\n[View Original Message]({jump})" if excerpt else (
        f"[View Original Message]({jump})"
    )

    period = WINDOW_FOOTER_LABELS.get(str(window), str(window).replace("_", " ").title())
    footer_text = (
        f"{period}  •  ▲ {message.upvote_count}  •  ▼ {message.downvote_count}"
        f"  •  Net {message.net_score}"
    )
    if len(footer_text) > 2048:
        footer_text = footer_text[:2045] + "…"

    embed: dict[str, Any] = {
        "title": f"#{rank} Trending",
        "description": description,
        "color": 0x5865F2,
        "fields": [
            {
                "name": "Source",
                "value": f"<#{message.channel_id}>",
                "inline": True,
            },
            {
                "name": "Posted",
                "value": f"<t:{ts}:f>",
                "inline": True,
            },
        ],
        "footer": {"text": footer_text},
    }

    display_name = (message.author_display_name or "").strip()
    avatar = (message.author_avatar_url or "").strip()
    if display_name:
        author_block: dict[str, Any] = {"name": display_name[:256], "url": jump}
        if avatar:
            author_block["icon_url"] = avatar[:1024]
        embed["author"] = author_block
    else:
        embed["fields"].insert(
            0,
            {
                "name": "Author",
                "value": f"<@{message.author_id}>",
                "inline": True,
            },
        )

    if normalized_media:
        embed["image"] = {"url": normalized_media}
    elif media:
        logger.warning(
            "Feed embed: skipped invalid media url message=%s",
            message.message_id,
        )

    # Unused emoji args kept for call-site compatibility / future field labels.
    _ = (upvote_emoji, downvote_emoji)
    return {"embeds": [embed]}


def desired_source_ids(top: list[FeedMessage]) -> list[str]:
    """Source message IDs in Discord send order (#1 best → #N)."""

    # top is already net DESC (best first); send in that order so #1 is at top.
    return [row.message_id for row in top]


def needs_full_rebuild(
    existing: list[FeedEntry],
    top: list[FeedMessage],
    channel_id: str,
) -> bool:
    """True when mapped order/set differs from desired ranked set."""

    desired = desired_source_ids(top)
    # Compare desired send order (#1→#N) against entries sorted by rank ascending.
    current = [
        entry.source_message_id
        for entry in sorted(existing, key=lambda e: e.rank)
        if entry.source_message_id
    ]
    if len(current) != len(desired):
        return True
    if current != desired:
        return True
    if any(entry.feed_channel_id != str(channel_id) for entry in existing):
        return True
    if any(entry.source_message_id is None for entry in existing):
        return True
    return False


async def acquire_rebuild_lock(guild_id: str, window: FeedWindow) -> bool:
    redis = await get_redis()
    try:
        return bool(
            await redis.set(feed_lock_key(guild_id, window), "1", nx=True, ex=90)
        )
    finally:
        await redis.aclose()


async def release_rebuild_lock(guild_id: str, window: FeedWindow) -> None:
    redis = await get_redis()
    try:
        await redis.delete(feed_lock_key(guild_id, window))
    finally:
        await redis.aclose()


async def rebuild_feed_window(
    session: AsyncSession,
    *,
    guild_id: str,
    window: FeedWindow,
    config: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Sync one feed window. Never raises Discord errors as uncaught 500s."""

    cfg = (
        merge_feed_config(config)
        if config is not None
        else await load_merged_feed_config(guild_id)
    )
    window_cfg = cfg["windows"].get(window) or {}
    channel_id = window_cfg.get("channel_id")
    if not window_cfg.get("enabled") or not channel_id:
        return {"ok": False, "reason": "window_not_configured", "window": window}

    if not await acquire_rebuild_lock(guild_id, window):
        return {"ok": False, "reason": "locked", "window": window}

    settings = get_settings()
    if not settings.discord_bot_token:
        await release_rebuild_lock(guild_id, window)
        return {"ok": False, "reason": "bot_token_missing", "window": window}

    messages_deleted = 0
    messages_restored = 0
    messages_updated = 0

    try:
        limit = clamp_display_limit(cfg.get("display_limit"))
        limit = min(limit, DISPLAY_LIMIT_MAX)
        min_net = int(cfg.get("min_net_score") or 1)
        top = await top_messages_for_window(
            session,
            guild_id=guild_id,
            window=window,
            min_net_score=min_net,
            limit=limit,
        )

        # Warm Redis ZSET for this window from PG result.
        redis = await get_redis()
        try:
            key = feed_rank_key(guild_id, window)
            await redis.delete(key)
            if top:
                mapping = {
                    row.message_id: composite_rank_score(
                        int(row.net_score),
                        int(row.upvote_count),
                        row.created_at,
                    )
                    for row in top
                }
                await redis.zadd(key, mapping)
        finally:
            await redis.aclose()

        existing = list(
            (
                await session.execute(
                    select(FeedEntry)
                    .where(
                        FeedEntry.guild_id == guild_id,
                        FeedEntry.window == window,
                    )
                    .order_by(FeedEntry.rank.asc())
                )
            )
            .scalars()
            .all()
        )

        up_key = emoji_reaction_key(cfg.get("upvote_emoji")) or "👍"
        down_key = emoji_reaction_key(cfg.get("downvote_emoji")) or "👎"

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)

            # Verify channel exists.
            try:
                await bot.get_channel(str(channel_id))
            except DiscordBotAPIError as error:
                if error.status_code == 404:
                    return {
                        "ok": False,
                        "reason": "feed_channel_missing",
                        "window": window,
                        "messages_deleted": 0,
                        "messages_restored": 0,
                        "messages_updated": 0,
                    }
                logger.exception(
                    "Feed channel check failed guild=%s window=%s",
                    guild_id,
                    window,
                )
                return {
                    "ok": False,
                    "reason": "discord_error",
                    "error": str(error),
                    "window": window,
                }

            do_rebuild = force or needs_full_rebuild(existing, top, str(channel_id))

            if do_rebuild:
                # Delete only Norgoth-owned feed messages.
                for entry in existing:
                    try:
                        await bot.delete_channel_message(
                            entry.feed_channel_id, entry.feed_message_id
                        )
                        messages_deleted += 1
                    except DiscordBotAPIError:
                        pass
                    await session.delete(entry)
                await session.flush()

                # Send #1→#N so best is at channel top. Rank labels stay 1=best.
                send_order = list(top)
                total = len(send_order)
                for index, source in enumerate(send_order):
                    rank = index + 1
                    await refresh_feed_message_media(bot, source)
                    payload = build_feed_embed(
                        rank=rank,
                        message=source,
                        upvote_emoji=up_key,
                        downvote_emoji=down_key,
                        window=window,
                    )
                    try:
                        created = await bot.send_channel_message(
                            str(channel_id), payload
                        )
                    except DiscordBotAPIError as error:
                        logger.exception(
                            "Feed send failed guild=%s window=%s rank=%s",
                            guild_id,
                            window,
                            rank,
                        )
                        await session.commit()
                        return {
                            "ok": False,
                            "reason": "discord_error",
                            "error": str(error),
                            "window": window,
                            "messages_deleted": messages_deleted,
                            "messages_restored": messages_restored,
                            "messages_updated": messages_updated,
                        }
                    feed_message_id = str(created.get("id") or "")
                    if not feed_message_id:
                        continue
                    session.add(
                        FeedEntry(
                            guild_id=guild_id,
                            window=window,
                            rank=rank,
                            feed_channel_id=str(channel_id),
                            feed_message_id=feed_message_id,
                            source_message_id=source.message_id,
                        )
                    )
                    messages_restored += 1
                    # Mild pacing to respect rate limits.
                    if index + 1 < total:
                        await asyncio.sleep(0.15)
            else:
                # Content-only refresh in place (same order).
                by_source = {
                    entry.source_message_id: entry
                    for entry in existing
                    if entry.source_message_id
                }
                for rank, source in enumerate(top, start=1):
                    entry = by_source.get(source.message_id)
                    if entry is None:
                        continue
                    await refresh_feed_message_media(bot, source)
                    payload = build_feed_embed(
                        rank=rank,
                        message=source,
                        upvote_emoji=up_key,
                        downvote_emoji=down_key,
                        window=window,
                    )
                    try:
                        await bot.edit_channel_message(
                            entry.feed_channel_id,
                            entry.feed_message_id,
                            payload,
                        )
                        entry.rank = rank
                        messages_updated += 1
                    except DiscordBotAPIError as error:
                        if error.status_code == 404:
                            logger.info(
                                "Feed slot missing guild=%s window=%s message=%s",
                                guild_id,
                                window,
                                entry.feed_message_id,
                            )
                            await session.rollback()
                            await release_rebuild_lock(guild_id, window)
                            return await rebuild_feed_window(
                                session,
                                guild_id=guild_id,
                                window=window,
                                config=cfg,
                                force=True,
                            )
                        logger.exception(
                            "Feed edit failed guild=%s window=%s",
                            guild_id,
                            window,
                        )
                        return {
                            "ok": False,
                            "reason": "discord_error",
                            "error": str(error),
                            "window": window,
                            "messages_deleted": messages_deleted,
                            "messages_restored": messages_restored,
                            "messages_updated": messages_updated,
                        }

        cfg.setdefault("last_refresh_at", {})[window] = now_iso()
        await save_config(
            guild_id, "feed_channels", cfg, enabled=bool(cfg.get("enabled"))
        )
        await session.commit()

        redis = await get_redis()
        try:
            await redis.srem(feed_dirty_key(guild_id), window)
        finally:
            await redis.aclose()

        logger.info(
            "Feed sync guild=%s window=%s filled=%s deleted=%s restored=%s updated=%s rebuild=%s",
            guild_id,
            window,
            len(top),
            messages_deleted,
            messages_restored,
            messages_updated,
            do_rebuild,
        )
        return {
            "ok": True,
            "window": window,
            "slots": len(top),
            "filled": len(top),
            "messages_deleted": messages_deleted,
            "messages_restored": messages_restored,
            "messages_updated": messages_updated,
            "rebuilt": do_rebuild,
        }
    except Exception as error:  # noqa: BLE001
        logger.exception(
            "Feed rebuild unexpected failure guild=%s window=%s", guild_id, window
        )
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {
            "ok": False,
            "reason": "unexpected_error",
            "error": str(error),
            "window": window,
            "messages_deleted": messages_deleted,
            "messages_restored": messages_restored,
            "messages_updated": messages_updated,
        }
    finally:
        await release_rebuild_lock(guild_id, window)


async def process_dirty_feeds(session: AsyncSession, guild_id: str) -> list[dict[str, Any]]:
    redis = await get_redis()
    try:
        dirty = [
            w.decode() if isinstance(w, bytes) else str(w)
            for w in await redis.smembers(feed_dirty_key(guild_id))
        ]
        ready: list[FeedWindow] = []
        for window in dirty:
            if window not in FEED_WINDOWS:
                continue
            if await redis.exists(feed_debounce_key(guild_id, window)):  # type: ignore[arg-type]
                continue
            ready.append(window)  # type: ignore[arg-type]
    finally:
        await redis.aclose()

    results: list[dict[str, Any]] = []
    cfg = await load_merged_feed_config(guild_id)
    for window in ready:
        results.append(
            await rebuild_feed_window(
                session, guild_id=guild_id, window=window, config=cfg
            )
        )
    return results


async def resolve_source_message_id(
    session: AsyncSession,
    *,
    guild_id: str,
    message_id: str,
) -> str:
    """If ``message_id`` is a feed slot, return its source; else return itself."""

    entry = (
        await session.execute(
            select(FeedEntry).where(
                FeedEntry.guild_id == guild_id,
                FeedEntry.feed_message_id == message_id,
            )
        )
    ).scalar_one_or_none()
    if entry and entry.source_message_id:
        return entry.source_message_id
    return message_id
