"""Per-guild honeypot (trap channel) configuration and trigger history."""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

router = APIRouter(
    tags=["Honeypot"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

HoneypotPunishment = Literal[
    "log_only",
    "delete",
    "timeout",
    "kick",
    "kick_purge",
    "ban",
]


def honeypot_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:honeypot"


def honeypot_triggers_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:honeypot:triggers"


class CreateChannelBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class HoneypotConfig(BaseModel):
    enabled: bool = False
    trap_channel_ids: list[str] = Field(default_factory=list, max_length=20)
    post_pinned_warning: bool = True
    warning_content: str = Field(
        default=(
            "⚠️ This channel is a honeypot trap. Do not post here. "
            "Posting will result in moderation action."
        ),
        max_length=2000,
    )
    warning_embed: Optional[dict[str, Any]] = None
    punishment: HoneypotPunishment = "kick"
    delete_history_hours: int = Field(default=0, ge=0, le=24)
    ignore_bots: bool = True
    exempt_role_ids: list[str] = Field(default_factory=list, max_length=50)
    exempt_member_ids: list[str] = Field(default_factory=list, max_length=100)
    log_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    ping_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    timeout_minutes: int = Field(default=60, ge=1, le=40320)


def load_stored_config(raw: str | None) -> dict[str, Any]:
    stored: dict[str, Any] = {}

    if not raw:
        return stored

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            stored = parsed
    except json.JSONDecodeError:
        pass

    return stored


@router.get("/guilds/{guild_id}/honeypot")
async def get_honeypot_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await read_raw(guild_id, "honeypot", redis_client)
    finally:
        await redis_client.aclose()

    stored = load_stored_config(raw)
    config = HoneypotConfig(**{
        key: value
        for key, value in stored.items()
        if key in HoneypotConfig.model_fields
    })

    result = {"guild_id": guild_id, **config.model_dump()}

    # Bot-managed fields preserved outside the Pydantic schema.
    for extra in (
        "warning_message_id",
        "warning_channel_id",
        "create_channel_request",
    ):
        if extra in stored:
            result[extra] = stored[extra]

    return result


@router.put("/guilds/{guild_id}/honeypot")
async def update_honeypot_config(
    guild_id: str,
    config: HoneypotConfig,
) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        existing = load_stored_config(await read_raw(guild_id, "honeypot", redis_client))
        payload = config.model_dump()
        payload["trap_channel_ids"] = [
            channel_id
            for channel_id in payload["trap_channel_ids"]
            if isinstance(channel_id, str) and channel_id.isdigit()
        ]
        payload["exempt_role_ids"] = [
            role_id
            for role_id in payload["exempt_role_ids"]
            if isinstance(role_id, str) and role_id.isdigit()
        ]
        payload["exempt_member_ids"] = [
            member_id
            for member_id in payload["exempt_member_ids"]
            if isinstance(member_id, str) and member_id.isdigit()
        ]
        # Preserve bot-managed bookkeeping across dashboard saves.
        for extra in (
            "warning_message_id",
            "warning_channel_id",
            "create_channel_request",
        ):
            if extra in existing and extra not in payload:
                payload[extra] = existing[extra]

        payload["updated_at"] = now_iso()
        await save_config(guild_id, "honeypot", payload, enabled=bool(payload.get("enabled", False)))
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}


@router.post("/guilds/{guild_id}/honeypot/create-channel")
async def request_honeypot_channel(
    guild_id: str,
    body: CreateChannelBody,
) -> dict[str, Any]:
    """Store a create-channel request for the bot to process on next sync."""

    redis_client = await get_redis()

    try:
        existing = load_stored_config(await read_raw(guild_id, "honeypot", redis_client))
        config = HoneypotConfig(**{
            key: value
            for key, value in existing.items()
            if key in HoneypotConfig.model_fields
        })
        payload = {**existing, **config.model_dump()}
        payload["create_channel_request"] = {
            "name": body.name.strip()[:100],
            "requested_at": now_iso(),
        }
        payload["updated_at"] = now_iso()
        await save_config(guild_id, "honeypot", payload, enabled=bool(payload.get("enabled", False)))
    finally:
        await redis_client.aclose()

    return {
        "guild_id": guild_id,
        "ok": True,
        "create_channel_request": payload["create_channel_request"],
    }


@router.get("/guilds/{guild_id}/honeypot/triggers")
async def get_honeypot_triggers(
    guild_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        total = await redis_client.llen(honeypot_triggers_key(guild_id))
        raw_entries = await redis_client.lrange(
            honeypot_triggers_key(guild_id),
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
