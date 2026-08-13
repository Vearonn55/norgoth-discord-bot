"""X / Twitter monthly soft budget for Content Notifications polling.

Operator sets ``X_MONTHLY_READ_BUDGET`` (integer metered reads per UTC month).
Empty or ``0`` disables the soft circuit (not recommended in production).
Filtered Stream / Activity API remain deferred until console-verified budget.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.services.content_notifications.queue import get_redis

X_READ_BUDGET_KEY = "norgoth:content_notifications:x:reads:{ym}"


def monthly_read_budget() -> int | None:
    raw = os.getenv("X_MONTHLY_READ_BUDGET", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _month_key(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return X_READ_BUDGET_KEY.format(ym=current.strftime("%Y-%m"))


async def current_read_count(redis_client: Redis | None = None) -> int:
    owns = redis_client is None
    client = redis_client or await get_redis()
    try:
        raw = await client.get(_month_key())
        return int(raw or 0)
    finally:
        if owns:
            await client.aclose()


async def budget_exhausted(redis_client: Redis | None = None) -> bool:
    limit = monthly_read_budget()
    if limit is None:
        return False
    return await current_read_count(redis_client) >= limit


async def record_reads(count: int = 1, redis_client: Redis | None = None) -> int:
    """Increment monthly read counter; returns new total."""

    if count <= 0:
        return await current_read_count(redis_client)
    owns = redis_client is None
    client = redis_client or await get_redis()
    try:
        key = _month_key()
        total = await client.incrby(key, count)
        # Expire ~40 days after first write in the month.
        await client.expire(key, 40 * 24 * 3600)
        return int(total)
    finally:
        if owns:
            await client.aclose()
