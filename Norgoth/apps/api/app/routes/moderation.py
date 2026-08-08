"""Moderation audit log, written by the bot to Redis."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis

router = APIRouter(
    tags=["Moderation"],
    dependencies=[Depends(guild_manager_dependency())],
)


def moderation_log_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:modlog"


@router.get("/guilds/{guild_id}/moderation-logs")
async def get_moderation_logs(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        raw_entries = await redis_client.lrange(
            moderation_log_key(guild_id),
            0,
            limit - 1,
        )
    finally:
        await redis_client.aclose()

    entries: list[dict[str, Any]] = []

    for raw in raw_entries:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            entries.append(parsed)

    return entries
