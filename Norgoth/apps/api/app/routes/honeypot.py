"""Per-guild honeypot (trap channel) configuration and trigger history."""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import (
    first_trap_channel_id,
    merge_honeypot_warning_fields,
    read_raw,
    save_config,
)

from app.core.content_limits import MAX_STORED_MARKDOWN_CHARS

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


class HoneypotConfig(BaseModel):
    enabled: bool = False
    trap_channel_ids: list[str] = Field(default_factory=list, max_length=20)
    post_pinned_warning: bool = True
    warning_content: str = Field(
        default=(
            "⚠️ This channel is a honeypot trap. Do not post here. "
            "Posting will result in moderation action."
        ),
        max_length=MAX_STORED_MARKDOWN_CHARS,
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


def resolve_force_warning_repost(
    existing: dict[str, Any],
    payload: dict[str, Any],
) -> bool:
    old_first = first_trap_channel_id(existing)
    new_first = first_trap_channel_id(payload)
    channel_changed = bool(old_first and new_first and old_first != new_first)
    posting = bool(payload.get("post_pinned_warning"))
    was_posting = bool(existing.get("post_pinned_warning"))
    flipped_on = posting and not was_posting
    ids_empty = not existing.get("warning_message_id")
    return bool(channel_changed or flipped_on or (posting and ids_empty))


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
        "warning_posted_at",
        "warning_pinned",
        "warning_status",
        "force_warning_repost",
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
        payload = merge_honeypot_warning_fields(existing, payload)
        payload.pop("create_channel_request", None)
        payload["force_warning_repost"] = resolve_force_warning_repost(
            existing, payload
        )

        payload["updated_at"] = now_iso()
        await save_config(guild_id, "honeypot", payload, enabled=bool(payload.get("enabled", False)))
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}


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
