"""Redis coordination for RSS worker (heartbeat + per-feed NX claim)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from redis.asyncio import Redis

RSS_WORKER_HEARTBEAT = "norgoth:rss:worker:heartbeat"
RSS_CLAIM_PREFIX = "norgoth:rss:claim:"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_redis() -> Redis:
    url = os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url, decode_responses=True)


async def heartbeat(ttl_seconds: int = 45) -> None:
    client = await get_redis()
    try:
        await client.set(RSS_WORKER_HEARTBEAT, now_iso(), ex=ttl_seconds)
    finally:
        await client.aclose()


async def worker_online() -> bool:
    client = await get_redis()
    try:
        return bool(await client.exists(RSS_WORKER_HEARTBEAT))
    finally:
        await client.aclose()


async def claim_feed(feed_id: str, *, ttl_seconds: int = 120) -> bool:
    client = await get_redis()
    try:
        result = await client.set(
            f"{RSS_CLAIM_PREFIX}{feed_id}",
            now_iso(),
            nx=True,
            ex=ttl_seconds,
        )
        return bool(result)
    finally:
        await client.aclose()


async def release_feed_claim(feed_id: str) -> None:
    client = await get_redis()
    try:
        await client.delete(f"{RSS_CLAIM_PREFIX}{feed_id}")
    finally:
        await client.aclose()
