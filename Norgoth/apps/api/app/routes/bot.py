"""Bot runtime health and Discord guild resources, backed by bot heartbeats."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis

router = APIRouter(tags=["Bot"])

BOT_HEARTBEAT_KEY = "norgoth:bot:heartbeat"
BOT_STATUS_KEY = "norgoth:bot:status"


def guild_resources_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:resources"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


def parse_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


@router.get("/bot/health")
async def get_bot_health() -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        heartbeat = await redis_client.get(BOT_HEARTBEAT_KEY)
        status = parse_json(await redis_client.get(BOT_STATUS_KEY))
    finally:
        await redis_client.aclose()

    connected = bool(heartbeat) and bool(status and status.get("connected"))

    return {
        "connected": connected,
        "heartbeat_at": heartbeat,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": status or {},
    }


@router.get(
    "/guilds/{guild_id}/discord-resources",
    dependencies=[Depends(guild_manager_dependency())],
)
async def get_guild_discord_resources(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        resources = parse_json(await redis_client.get(guild_resources_key(guild_id)))
    finally:
        await redis_client.aclose()

    if resources is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No Discord resources found for this guild. "
                "Make sure the bot is running and invited to the server."
            ),
        )

    return resources


@router.get(
    "/guilds/{guild_id}/members",
    dependencies=[Depends(guild_manager_dependency())],
)
async def get_guild_members(guild_id: str) -> dict[str, Any]:
    """Member snapshot published by the bot (used for DM campaign targeting)."""

    redis_client = await get_redis()

    try:
        snapshot = parse_json(await redis_client.get(guild_members_key(guild_id)))
    finally:
        await redis_client.aclose()

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No member snapshot found for this guild. "
                "Make sure the bot is running with the members intent enabled."
            ),
        )

    return snapshot
