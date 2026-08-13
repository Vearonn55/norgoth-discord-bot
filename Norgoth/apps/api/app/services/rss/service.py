"""Probe + bootstrap helpers for RSS feeds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rss_feeds import RssFeedConfig, RssFeedItem
from app.security.ssrf import SsrfError, safe_fetch
from app.services.rss.parser import FeedParseError, ParsedFeed, parse_feed
from app.services.rss.quotas import (
    MAX_ITEMS_RETAINED,
    clamp_poll_interval,
    feed_url_hash,
    next_poll_after_success,
)


@dataclass
class ProbeResult:
    ok: bool
    error: str | None
    format_hint: str | None
    feed_title: str | None
    sample_title: str | None
    item_count: int
    etag: str | None
    last_modified: str | None
    final_url: str | None
    parsed: ParsedFeed | None


async def probe_feed_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> ProbeResult:
    try:
        result = await safe_fetch(url, client=client)
    except SsrfError as exc:
        return ProbeResult(
            ok=False,
            error=str(exc),
            format_hint=None,
            feed_title=None,
            sample_title=None,
            item_count=0,
            etag=None,
            last_modified=None,
            final_url=None,
            parsed=None,
        )
    except httpx.HTTPError as exc:
        return ProbeResult(
            ok=False,
            error=f"Fetch failed: {exc}",
            format_hint=None,
            feed_title=None,
            sample_title=None,
            item_count=0,
            etag=None,
            last_modified=None,
            final_url=None,
            parsed=None,
        )

    if result.status_code >= 400:
        return ProbeResult(
            ok=False,
            error=f"Feed returned HTTP {result.status_code}",
            format_hint=None,
            feed_title=None,
            sample_title=None,
            item_count=0,
            etag=result.headers.get("etag"),
            last_modified=result.headers.get("last-modified"),
            final_url=result.final_url,
            parsed=None,
        )

    try:
        parsed = parse_feed(result.body)
    except FeedParseError as exc:
        return ProbeResult(
            ok=False,
            error=str(exc),
            format_hint=None,
            feed_title=None,
            sample_title=None,
            item_count=0,
            etag=result.headers.get("etag"),
            last_modified=result.headers.get("last-modified"),
            final_url=result.final_url,
            parsed=None,
        )

    sample = parsed.items[0].title if parsed.items else None
    return ProbeResult(
        ok=True,
        error=None,
        format_hint=parsed.format_hint,
        feed_title=parsed.title,
        sample_title=sample,
        item_count=len(parsed.items),
        etag=result.headers.get("etag"),
        last_modified=result.headers.get("last-modified"),
        final_url=result.final_url,
        parsed=parsed,
    )


async def bootstrap_items(
    session: AsyncSession,
    feed: RssFeedConfig,
    parsed: ParsedFeed,
) -> int:
    """Mark current items as seen without publishing. Returns count inserted."""

    now = datetime.now(timezone.utc)
    inserted = 0
    for item in parsed.items:
        existing = await session.scalar(
            select(RssFeedItem.id).where(
                RssFeedItem.feed_id == feed.id,
                RssFeedItem.item_key == item.item_key,
            )
        )
        if existing:
            continue
        session.add(
            RssFeedItem(
                feed_id=feed.id,
                item_key=item.item_key,
                published_at=item.published,
                first_seen_at=now,
                skipped_reason="bootstrap",
            )
        )
        inserted += 1
    await session.flush()
    return inserted


async def prune_old_items(session: AsyncSession, feed_id: UUID) -> None:
    """Keep the newest MAX_ITEMS_RETAINED rows per feed."""

    count = await session.scalar(
        select(func.count()).select_from(RssFeedItem).where(
            RssFeedItem.feed_id == feed_id
        )
    )
    if not count or count <= MAX_ITEMS_RETAINED:
        return

    # Delete oldest beyond retention.
    excess = int(count) - MAX_ITEMS_RETAINED
    oldest_ids = (
        await session.scalars(
            select(RssFeedItem.id)
            .where(RssFeedItem.feed_id == feed_id)
            .order_by(RssFeedItem.first_seen_at.asc())
            .limit(excess)
        )
    ).all()
    if oldest_ids:
        await session.execute(
            delete(RssFeedItem).where(RssFeedItem.id.in_(list(oldest_ids)))
        )


def serialize_feed(feed: RssFeedConfig) -> dict[str, Any]:
    return {
        "id": str(feed.id),
        "guild_id": feed.guild_id,
        "feed_url": feed.feed_url,
        "display_name": feed.display_name,
        "channel_id": feed.channel_id,
        "mention_role_id": feed.mention_role_id,
        "enabled": bool(feed.enabled),
        "poll_interval_seconds": int(feed.poll_interval_seconds),
        "format_hint": feed.format_hint,
        "next_poll_at": feed.next_poll_at.isoformat() if feed.next_poll_at else None,
        "last_success_at": (
            feed.last_success_at.isoformat() if feed.last_success_at else None
        ),
        "last_error": feed.last_error,
        "failure_count": int(feed.failure_count or 0),
        "created_at": feed.created_at.isoformat() if feed.created_at else None,
        "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
    }


# re-export for routes
__all__ = [
    "ProbeResult",
    "bootstrap_items",
    "clamp_poll_interval",
    "feed_url_hash",
    "next_poll_after_success",
    "probe_feed_url",
    "prune_old_items",
    "serialize_feed",
]
