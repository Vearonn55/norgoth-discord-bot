"""Shared helper for writing bot-read Redis snapshots after a Postgres commit.

The architecture keeps Postgres as the source of truth and Redis as a cache the
bot reads. Every config domain follows the same contract: the API writes durable
state inside a transaction, commits, then rewrites the exact per-guild Redis key
the bot already reads (``norgoth:guild:{guild_id}:{suffix}``). This module
generalises the pattern first introduced by the logging routing snapshot so all
domains write snapshots identically.

Because the request-scoped session uses ``expire_on_commit=False`` and never
commits inside the dependency, callers own the commit boundary and must call the
snapshot writer *after* ``await session.commit()``.
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis.asyncio as redis

REDIS_URL = os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0")

_GUILD_KEY_PREFIX = "norgoth:guild:"


def guild_key(guild_id: str, suffix: str) -> str:
    """Return the canonical per-guild Redis key for a snapshot ``suffix``."""

    return f"{_GUILD_KEY_PREFIX}{guild_id}:{suffix}"


async def get_redis() -> redis.Redis:
    """Return a decoded-responses Redis client."""

    return redis.from_url(REDIS_URL, decode_responses=True)


async def write_snapshot(
    guild_id: str,
    suffix: str,
    payload: Any,
    *,
    redis_client: redis.Redis | None = None,
) -> None:
    """Serialise ``payload`` to JSON and store it at the guild snapshot key.

    Args:
        guild_id: The Discord guild snowflake.
        suffix: The key suffix (for example ``"automod"`` or ``"logging:routing"``).
        payload: A JSON-serialisable snapshot the bot consumes.
        redis_client: Optional client to reuse; when omitted a client is created
            and closed for this call.
    """

    owns_client = redis_client is None
    client = redis_client or await get_redis()
    try:
        await client.set(guild_key(guild_id, suffix), json.dumps(payload))
    finally:
        if owns_client:
            await client.aclose()


async def delete_snapshot(
    guild_id: str,
    suffix: str,
    *,
    redis_client: redis.Redis | None = None,
) -> None:
    """Delete a guild snapshot key (used when a feature is fully removed)."""

    owns_client = redis_client is None
    client = redis_client or await get_redis()
    try:
        await client.delete(guild_key(guild_id, suffix))
    finally:
        if owns_client:
            await client.aclose()
