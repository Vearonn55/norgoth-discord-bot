"""Flush now-stale per-guild config snapshot keys from Redis (dev reset).

After the Postgres-source-of-truth migration, config snapshots are rehydrated
from Postgres on read. This removes the old per-guild config keys (and legacy
logging keys) so nothing stale lingers. Runtime caches (xp, incidents, ticket
records) are left untouched.

Usage:
    python -m scripts.flush_stale_redis
"""

from __future__ import annotations

import asyncio

from app.services.snapshot_writer import get_redis

STALE_SUFFIXES = [
    "modules",
    "automation",
    "automod",
    "raid",
    "honeypot",
    "leveling:config",
    "autoresponses",
    "rolemenus",
    "tickets:config",
    "logging",
    "logging:routing",
]


async def main() -> None:
    client = await get_redis()
    deleted = 0
    try:
        for suffix in STALE_SUFFIXES:
            pattern = f"norgoth:guild:*:{suffix}"
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                deleted += 1
    finally:
        await client.aclose()
    print(f"Deleted {deleted} stale config keys.")


if __name__ == "__main__":
    asyncio.run(main())
