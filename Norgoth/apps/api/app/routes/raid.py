"""Per-guild raid protection configuration and incident history."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso

router = APIRouter(
    tags=["Raid"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"


def raid_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:raid"


def raid_incidents_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:raid:incidents"


def raid_incident_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:raid:incident"


class RaidConfig(BaseModel):
    enabled: bool = False
    alert_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    joins_per_minute: int = Field(default=10, ge=2, le=200)
    young_account_age_days: int = Field(default=7, ge=1, le=365)
    young_account_ratio: int = Field(default=50, ge=0, le=100)
    response_duration_minutes: int = Field(default=30, ge=1, le=1440)
    respond_automatically: bool = False
    pause_invites: bool = False
    force_verification: bool = False
    kick_young_accounts: bool = False
    pause_invite_crediting: bool = False


@router.get("/guilds/{guild_id}/raid")
async def get_raid_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(raid_key(guild_id))
        active_raw = await redis_client.get(raid_incident_key(guild_id))
    finally:
        await redis_client.aclose()

    stored: dict[str, Any] = {}

    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                stored = parsed
        except json.JSONDecodeError:
            pass

    config = RaidConfig(**{
        key: value
        for key, value in stored.items()
        if key in RaidConfig.model_fields
    })

    active_incident: dict[str, Any] | None = None
    if active_raw:
        try:
            parsed = json.loads(active_raw)
            if isinstance(parsed, dict):
                active_incident = parsed
        except json.JSONDecodeError:
            pass

    return {
        "guild_id": guild_id,
        **config.model_dump(),
        "active_incident": active_incident,
    }


@router.put("/guilds/{guild_id}/raid")
async def update_raid_config(
    guild_id: str,
    config: RaidConfig,
) -> dict[str, Any]:
    payload = config.model_dump()
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await redis_client.set(raid_key(guild_id), json.dumps(payload))
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}


@router.get("/guilds/{guild_id}/raid/incidents")
async def get_raid_incidents(
    guild_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        total = await redis_client.llen(raid_incidents_key(guild_id))
        raw_entries = await redis_client.lrange(
            raid_incidents_key(guild_id),
            offset,
            offset + limit - 1,
        )
    finally:
        await redis_client.aclose()

    items: list[dict[str, Any]] = []

    for raw in raw_entries:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            items.append(parsed)

    return {
        "guild_id": guild_id,
        "items": items,
        "total": int(total or 0),
        "offset": offset,
        "limit": limit,
    }
