"""Redis queue helpers for content notification delivery jobs."""

from __future__ import annotations

import os
from typing import Any

from redis.asyncio import Redis

CONTENT_NOTIFICATION_QUEUE = "norgoth:content_notifications:queue"
CONTENT_NOTIFICATION_HEARTBEAT = "norgoth:content_notifications:worker:heartbeat"
CONTENT_NOTIFICATION_REPLAY = "norgoth:content_notifications:replay"
CONTENT_NOTIFICATION_CIRCUIT = "norgoth:content_notifications:circuit:{platform}"


async def get_redis() -> Redis:
    url = os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url, decode_responses=True)


async def enqueue_job(job_id: str) -> None:
    client = await get_redis()
    try:
        await client.lpush(CONTENT_NOTIFICATION_QUEUE, job_id)
    finally:
        await client.aclose()


async def pop_job(timeout_seconds: int = 2) -> str | None:
    client = await get_redis()
    try:
        item = await client.brpop(CONTENT_NOTIFICATION_QUEUE, timeout=timeout_seconds)
        if not item:
            return None
        return item[1]
    finally:
        await client.aclose()


async def heartbeat(ttl_seconds: int = 45) -> None:
    client = await get_redis()
    try:
        await client.set(CONTENT_NOTIFICATION_HEARTBEAT, "1", ex=ttl_seconds)
    finally:
        await client.aclose()


async def mark_replay(message_id: str, *, ttl_seconds: int = 86_400) -> bool:
    """Return True if message_id is new; False if already seen."""

    client = await get_redis()
    try:
        created = await client.set(
            f"{CONTENT_NOTIFICATION_REPLAY}:{message_id}",
            "1",
            nx=True,
            ex=ttl_seconds,
        )
        return bool(created)
    finally:
        await client.aclose()


async def is_circuit_open(platform: str) -> bool:
    client = await get_redis()
    try:
        return bool(await client.exists(CONTENT_NOTIFICATION_CIRCUIT.format(platform=platform)))
    finally:
        await client.aclose()


async def open_circuit(platform: str, *, ttl_seconds: int = 300) -> None:
    client = await get_redis()
    try:
        await client.set(
            CONTENT_NOTIFICATION_CIRCUIT.format(platform=platform),
            "1",
            ex=ttl_seconds,
        )
    finally:
        await client.aclose()


async def worker_online() -> bool:
    client = await get_redis()
    try:
        return bool(await client.exists(CONTENT_NOTIFICATION_HEARTBEAT))
    finally:
        await client.aclose()
