"""RSS feed quotas and scheduling helpers."""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rss_feeds import RssFeedConfig

MAX_FEEDS_PER_GUILD = 15
MIN_POLL_INTERVAL_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 300
MAX_POSTS_PER_POLL = 5
MAX_ITEMS_RETAINED = 500
CLAIM_TTL_SECONDS = 120
MAX_BACKOFF_SECONDS = 6 * 3600

RSS_FEED_LIMIT_REACHED = "rss_feed_limit_reached"

logger = logging.getLogger("norgoth.rss.quotas")


def feed_url_hash(url: str) -> str:
    normalized = url.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def clamp_poll_interval(seconds: int | None) -> int:
    value = int(seconds) if seconds is not None else DEFAULT_POLL_INTERVAL_SECONDS
    return max(MIN_POLL_INTERVAL_SECONDS, value)


def next_poll_after_success(
    interval_seconds: int,
    *,
    now: datetime | None = None,
) -> datetime:
    base = now or datetime.now(timezone.utc)
    jitter = random.randint(0, min(60, max(0, interval_seconds // 10)))
    return base + timedelta(seconds=interval_seconds + jitter)


def next_poll_after_failure(
    failure_count: int,
    interval_seconds: int,
    *,
    now: datetime | None = None,
) -> datetime:
    base = now or datetime.now(timezone.utc)
    # exponential: interval * 2^n capped
    exp = min(failure_count, 6)
    delay = min(interval_seconds * (2**exp), MAX_BACKOFF_SECONDS)
    jitter = random.randint(0, min(60, delay // 10 or 1))
    return base + timedelta(seconds=delay + jitter)


class RssFeedQuotaError(Exception):
    """Raised when creating a feed would exceed the per-guild cap."""

    def __init__(self, *, limit: int, current: int, message: str) -> None:
        super().__init__(message)
        self.code = RSS_FEED_LIMIT_REACHED
        self.limit = limit
        self.current = current
        self.message = message

    def as_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "limit": self.limit,
            "current": self.current,
        }


def _guild_advisory_lock_key(guild_id: str) -> int:
    digest = hashlib.blake2b(
        f"norgoth:rss:{guild_id}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


async def count_guild_feeds(session: AsyncSession, guild_id: str) -> int:
    """Count all configured feeds for a guild, including disabled rows."""

    count = await session.scalar(
        select(func.count())
        .select_from(RssFeedConfig)
        .where(RssFeedConfig.guild_id == guild_id)
    )
    return int(count or 0)


async def assert_can_create_rss_feed(
    session: AsyncSession,
    *,
    guild_id: str,
) -> None:
    """Lock the guild and reject a 16th feed. Disabled feeds count."""

    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _guild_advisory_lock_key(guild_id)},
    )
    current = await count_guild_feeds(session, guild_id)
    if current >= MAX_FEEDS_PER_GUILD:
        logger.info(
            "rss_feed_limit_reached guild_id=%s current=%s limit=%s",
            guild_id,
            current,
            MAX_FEEDS_PER_GUILD,
        )
        raise RssFeedQuotaError(
            limit=MAX_FEEDS_PER_GUILD,
            current=current,
            message=(
                f"Maximum of {MAX_FEEDS_PER_GUILD} RSS feeds per server "
                "(including disabled)."
            ),
        )
