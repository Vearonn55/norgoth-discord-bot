"""Invite tracking: inviter leaderboard and recent joins with attribution."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis

router = APIRouter(
    tags=["Invites"],
    dependencies=[Depends(guild_manager_dependency())],
)


def invite_counters_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:invites:counters"


def invite_recent_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:invites:recent"


@router.get("/guilds/{guild_id}/invites/leaderboard")
async def get_invite_leaderboard(guild_id: str) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        counters = await redis_client.hgetall(invite_counters_key(guild_id))
    finally:
        await redis_client.aclose()

    leaderboard: list[dict[str, Any]] = []

    for inviter_id, raw in counters.items():
        try:
            counter = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(counter, dict):
            continue

        joins = int(counter.get("joins", 0))
        leaves = int(counter.get("leaves", 0))

        leaderboard.append(
            {
                "inviter_id": str(inviter_id),
                "name": str(counter.get("name") or inviter_id),
                "joins": joins,
                "leaves": leaves,
                "rejoins": int(counter.get("rejoins", 0)),
                "net": max(0, joins - leaves),
            }
        )

    leaderboard.sort(key=lambda entry: entry["net"], reverse=True)

    for index, entry in enumerate(leaderboard, start=1):
        entry["rank"] = index

    return leaderboard


@router.get("/guilds/{guild_id}/invites/recent")
async def get_recent_joins(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        raw_entries = await redis_client.lrange(
            invite_recent_key(guild_id),
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
