"""Feed Channels persistence: track messages, canonical votes, author rollups."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed_channels import FeedAuthorStats, FeedEntry, FeedMessage, FeedVote
from app.services.feed_ranking import (
    FeedWindow,
    composite_rank_score,
    feed_author_net_key,
    feed_debounce_key,
    feed_dirty_key,
    feed_rank_key,
    windows_for_timestamp,
)
from app.services.campaign_store import get_redis

logger = logging.getLogger("norgoth.feed")

VoteType = Literal["up", "down"]


async def track_feed_message(
    session: AsyncSession,
    *,
    guild_id: str,
    channel_id: str,
    message_id: str,
    author_id: str,
    created_at: datetime,
    content_excerpt: str | None,
    attachment_count: int = 0,
    primary_media_url: str | None = None,
    author_display_name: str | None = None,
    author_avatar_url: str | None = None,
) -> FeedMessage:
    existing = (
        await session.execute(
            select(FeedMessage).where(
                FeedMessage.guild_id == guild_id,
                FeedMessage.message_id == message_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status == "deleted":
            return existing
        existing.content_excerpt = content_excerpt
        existing.attachment_count = attachment_count
        if primary_media_url is not None:
            existing.primary_media_url = (primary_media_url or "")[:1024] or None
        if author_display_name is not None:
            existing.author_display_name = (author_display_name or "")[:128] or None
        if author_avatar_url is not None:
            existing.author_avatar_url = (author_avatar_url or "")[:1024] or None
        return existing

    row = FeedMessage(
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=message_id,
        author_id=author_id,
        author_display_name=(author_display_name or "")[:128] or None,
        author_avatar_url=(author_avatar_url or "")[:1024] or None,
        created_at=created_at
        if created_at.tzinfo
        else created_at.replace(tzinfo=timezone.utc),
        content_excerpt=(content_excerpt or "")[:500] or None,
        primary_media_url=(primary_media_url or "")[:1024] or None,
        attachment_count=max(0, int(attachment_count)),
        status="active",
    )
    session.add(row)

    stats = await _get_or_create_author_stats(session, guild_id, author_id)
    stats.post_count = int(stats.post_count) + 1
    await session.flush()
    return row


async def mark_feed_message_deleted(
    session: AsyncSession,
    *,
    guild_id: str,
    message_id: str,
) -> FeedMessage | None:
    row = (
        await session.execute(
            select(FeedMessage)
            .where(
                FeedMessage.guild_id == guild_id,
                FeedMessage.message_id == message_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None or row.status == "deleted":
        return row

    # Reverse author contribution from this message's current scores.
    stats = await _get_or_create_author_stats(session, guild_id, row.author_id)
    stats.net_score = int(stats.net_score) - int(row.net_score)
    stats.upvote_total = max(0, int(stats.upvote_total) - int(row.upvote_count))
    stats.downvote_total = max(0, int(stats.downvote_total) - int(row.downvote_count))
    stats.post_count = max(0, int(stats.post_count) - 1)

    row.status = "deleted"
    row.upvote_count = 0
    row.downvote_count = 0
    row.net_score = 0

    # Clear source from feed slots (rebuild will refresh embeds).
    entries = (
        await session.execute(
            select(FeedEntry).where(
                FeedEntry.guild_id == guild_id,
                FeedEntry.source_message_id == message_id,
            )
        )
    ).scalars().all()
    for entry in entries:
        entry.source_message_id = None

    await session.flush()
    return row


async def update_feed_message_excerpt(
    session: AsyncSession,
    *,
    guild_id: str,
    message_id: str,
    content_excerpt: str | None,
    attachment_count: int | None = None,
    primary_media_url: str | None = None,
    author_display_name: str | None = None,
    author_avatar_url: str | None = None,
) -> FeedMessage | None:
    row = (
        await session.execute(
            select(FeedMessage).where(
                FeedMessage.guild_id == guild_id,
                FeedMessage.message_id == message_id,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status != "active":
        return row
    row.content_excerpt = (content_excerpt or "")[:500] or None
    if attachment_count is not None:
        row.attachment_count = max(0, int(attachment_count))
    if primary_media_url is not None:
        row.primary_media_url = (primary_media_url or "")[:1024] or None
    if author_display_name is not None:
        row.author_display_name = (author_display_name or "")[:128] or None
    if author_avatar_url is not None:
        row.author_avatar_url = (author_avatar_url or "")[:1024] or None
    await session.flush()
    return row


async def apply_feed_vote(
    session: AsyncSession,
    *,
    guild_id: str,
    message_id: str,
    voter_id: str,
    vote: VoteType | None,
) -> dict[str, Any]:
    """Upsert or clear a canonical vote. ``vote=None`` removes the vote."""

    message = (
        await session.execute(
            select(FeedMessage)
            .where(
                FeedMessage.guild_id == guild_id,
                FeedMessage.message_id == message_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if message is None or message.status != "active":
        return {"ok": False, "reason": "message_not_tracked"}

    existing = (
        await session.execute(
            select(FeedVote)
            .where(
                FeedVote.guild_id == guild_id,
                FeedVote.message_id == message_id,
                FeedVote.voter_id == voter_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    previous: VoteType | None = None
    if existing is not None:
        previous = existing.vote  # type: ignore[assignment]

    old_up = int(message.upvote_count)
    old_down = int(message.downvote_count)
    old_net = int(message.net_score)

    if vote is None:
        if existing is None:
            return {
                "ok": True,
                "changed": False,
                "previous": previous,
                "vote": None,
                "message": _message_payload(message),
            }
        await session.delete(existing)
        _adjust_counts(message, previous, None)
    elif existing is None:
        session.add(
            FeedVote(
                guild_id=guild_id,
                message_id=message_id,
                voter_id=voter_id,
                vote=vote,
            )
        )
        _adjust_counts(message, None, vote)
    elif existing.vote == vote:
        return {
            "ok": True,
            "changed": False,
            "previous": previous,
            "vote": vote,
            "message": _message_payload(message),
        }
    else:
        existing.vote = vote
        _adjust_counts(message, previous, vote)

    message.net_score = int(message.upvote_count) - int(message.downvote_count)

    stats = await _get_or_create_author_stats(session, guild_id, message.author_id)
    stats.net_score = int(stats.net_score) - old_net + int(message.net_score)
    stats.upvote_total = int(stats.upvote_total) - old_up + int(message.upvote_count)
    stats.downvote_total = (
        int(stats.downvote_total) - old_down + int(message.downvote_count)
    )

    await session.flush()
    return {
        "ok": True,
        "changed": True,
        "previous": previous,
        "vote": vote,
        "message": _message_payload(message),
        "author_id": message.author_id,
        "author_net": int(stats.net_score),
    }


def _adjust_counts(
    message: FeedMessage,
    previous: VoteType | None,
    new: VoteType | None,
) -> None:
    if previous == "up":
        message.upvote_count = max(0, int(message.upvote_count) - 1)
    elif previous == "down":
        message.downvote_count = max(0, int(message.downvote_count) - 1)
    if new == "up":
        message.upvote_count = int(message.upvote_count) + 1
    elif new == "down":
        message.downvote_count = int(message.downvote_count) + 1


def _message_payload(message: FeedMessage) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "channel_id": message.channel_id,
        "author_id": message.author_id,
        "created_at": message.created_at.isoformat(),
        "upvote_count": int(message.upvote_count),
        "downvote_count": int(message.downvote_count),
        "net_score": int(message.net_score),
        "status": message.status,
        "content_excerpt": message.content_excerpt,
        "attachment_count": int(message.attachment_count),
    }


async def _get_or_create_author_stats(
    session: AsyncSession,
    guild_id: str,
    user_id: str,
) -> FeedAuthorStats:
    row = (
        await session.execute(
            select(FeedAuthorStats)
            .where(
                FeedAuthorStats.guild_id == guild_id,
                FeedAuthorStats.user_id == user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = FeedAuthorStats(guild_id=guild_id, user_id=user_id)
        session.add(row)
        await session.flush()
    return row


async def mark_windows_dirty(
    guild_id: str,
    created_at: datetime,
    *,
    debounce_seconds: int = 45,
) -> list[FeedWindow]:
    windows = windows_for_timestamp(created_at)
    redis = await get_redis()
    try:
        dirty = feed_dirty_key(guild_id)
        for window in windows:
            await redis.sadd(dirty, window)
            await redis.set(
                feed_debounce_key(guild_id, window),
                "1",
                ex=debounce_seconds,
                nx=True,
            )
    finally:
        await redis.aclose()
    return windows


async def warm_message_rank_cache(
    guild_id: str,
    message: FeedMessage,
) -> None:
    if message.status != "active":
        await remove_message_from_rank_cache(guild_id, message.message_id)
        return
    redis = await get_redis()
    try:
        score = composite_rank_score(
            int(message.net_score),
            int(message.upvote_count),
            message.created_at,
        )
        pipe = redis.pipeline()
        for window in windows_for_timestamp(message.created_at):
            pipe.zadd(feed_rank_key(guild_id, window), {message.message_id: score})
        await pipe.execute()
    finally:
        await redis.aclose()


async def remove_message_from_rank_cache(guild_id: str, message_id: str) -> None:
    redis = await get_redis()
    try:
        pipe = redis.pipeline()
        for window in ("daily", "weekly", "monthly", "all_time"):
            pipe.zrem(feed_rank_key(guild_id, window), message_id)  # type: ignore[arg-type]
        await pipe.execute()
    finally:
        await redis.aclose()


async def warm_author_net_cache(
    guild_id: str,
    user_id: str,
    net_score: int,
) -> None:
    redis = await get_redis()
    try:
        key = feed_author_net_key(guild_id)
        if net_score == 0:
            await redis.zrem(key, user_id)
        else:
            await redis.zadd(key, {user_id: float(net_score)})
    finally:
        await redis.aclose()
