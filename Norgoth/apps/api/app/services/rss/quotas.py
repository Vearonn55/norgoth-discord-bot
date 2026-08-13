"""RSS feed quotas and scheduling helpers."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

MAX_FEEDS_PER_GUILD = 5
MIN_POLL_INTERVAL_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 300
MAX_POSTS_PER_POLL = 5
MAX_ITEMS_RETAINED = 500
CLAIM_TTL_SECONDS = 120
MAX_BACKOFF_SECONDS = 6 * 3600


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
