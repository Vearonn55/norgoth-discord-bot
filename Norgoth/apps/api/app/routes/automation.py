"""Per-guild automation configuration (welcome/leave flow, auto-role, mod log)."""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

router = APIRouter(
    tags=["Automation"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

DISCORD_API_BASE_URL = "https://discord.com/api/v10"


def automation_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:automation"


def welcome_status_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:welcome:status"


def autorole_status_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:autorole:status"


def guild_resources_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:resources"


class AutomationConfig(BaseModel):
    welcome_enabled: bool = False
    welcome_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    welcome_message: str = Field(
        default="Welcome to {server}, {user}!",
        max_length=1500,
    )
    # "text" sends welcome_message; "embed" renders the referenced Embed Draft.
    welcome_source: Literal["text", "embed"] = "text"
    welcome_embed_message_id: Optional[str] = Field(default=None, max_length=64)
    leave_enabled: bool = False
    leave_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    leave_message: str = Field(
        default="{username} has left {server}.",
        max_length=1500,
    )
    leave_source: Literal["text", "embed"] = "text"
    leave_embed_message_id: Optional[str] = Field(default=None, max_length=64)
    auto_role_enabled: bool = False
    auto_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    auto_role_ids: list[str] = Field(default_factory=list, max_length=50)
    mod_log_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)


class AutomationConfigPatch(BaseModel):
    """Partial automation update.

    Every field is optional so a single section (Welcome or Leave) can be saved
    without resubmitting — and therefore without clobbering — the other
    section's stored values. Fields are merged server-side onto the durable
    config, using ``exclude_unset`` to distinguish "leave unchanged" from an
    explicit ``null`` clear.
    """

    welcome_enabled: Optional[bool] = None
    welcome_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    welcome_message: Optional[str] = Field(default=None, max_length=1500)
    welcome_source: Optional[Literal["text", "embed"]] = None
    welcome_embed_message_id: Optional[str] = Field(default=None, max_length=64)
    leave_enabled: Optional[bool] = None
    leave_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    leave_message: Optional[str] = Field(default=None, max_length=1500)
    leave_source: Optional[Literal["text", "embed"]] = None
    leave_embed_message_id: Optional[str] = Field(default=None, max_length=64)
    auto_role_enabled: Optional[bool] = None
    auto_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    auto_role_ids: Optional[list[str]] = Field(default=None, max_length=50)
    mod_log_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)


def normalize_auto_roles(payload: dict[str, Any]) -> dict[str, Any]:
    """Prefer auto_role_ids; migrate legacy auto_role_id into the list."""

    role_ids = [
        role_id
        for role_id in payload.get("auto_role_ids") or []
        if isinstance(role_id, str) and role_id.isdigit()
    ]

    legacy = payload.get("auto_role_id")
    if isinstance(legacy, str) and legacy.isdigit() and legacy not in role_ids:
        role_ids.insert(0, legacy)

    payload["auto_role_ids"] = role_ids[:50]
    payload["auto_role_id"] = role_ids[0] if role_ids else None
    return payload


async def read_stored_config(redis_client, guild_id: str) -> AutomationConfig:
    raw = await read_raw(guild_id, "automation", redis_client)

    if raw:
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            stored = {}
    else:
        stored = {}

    if not isinstance(stored, dict):
        stored = {}

    stored = normalize_auto_roles(dict(stored))

    return AutomationConfig(**{
        key: value
        for key, value in stored.items()
        if key in AutomationConfig.model_fields
    })


@router.get("/guilds/{guild_id}/automation")
async def get_automation_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        config = await read_stored_config(redis_client, guild_id)
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **config.model_dump()}


@router.put("/guilds/{guild_id}/automation")
async def update_automation_config(
    guild_id: str,
    config: AutomationConfig,
) -> dict[str, Any]:
    payload = normalize_auto_roles(config.model_dump())
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await save_config(guild_id, "automation", payload)
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}


@router.patch("/guilds/{guild_id}/automation")
async def patch_automation_config(
    guild_id: str,
    patch: AutomationConfigPatch,
) -> dict[str, Any]:
    """Merge a partial update onto the stored config, section-safe.

    Only the fields explicitly present in the request body are changed; the
    rest of the durable config (including the other message section) is read
    from storage and preserved. This is what makes saving Welcome independent
    of unsaved Leave edits, and vice versa.
    """

    updates = patch.model_dump(exclude_unset=True)

    redis_client = await get_redis()

    try:
        current = await read_stored_config(redis_client, guild_id)
        merged = {**current.model_dump(), **updates}
        merged = normalize_auto_roles(merged)
        # Re-validate the merged shape so patch inputs get the same guarantees
        # as a full PUT before it is persisted.
        final = AutomationConfig(
            **{
                key: value
                for key, value in merged.items()
                if key in AutomationConfig.model_fields
            }
        )
        payload = final.model_dump()
        payload["updated_at"] = now_iso()
        await save_config(guild_id, "automation", payload)
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}


@router.get("/guilds/{guild_id}/automation/status")
async def get_automation_status(guild_id: str) -> dict[str, Any]:
    """Last welcome / auto-role attempt reported by the bot."""

    redis_client = await get_redis()

    try:
        welcome_raw = await redis_client.get(welcome_status_key(guild_id))
        autorole_raw = await redis_client.get(autorole_status_key(guild_id))
    finally:
        await redis_client.aclose()

    welcome = None
    if welcome_raw:
        try:
            welcome = json.loads(welcome_raw)
        except json.JSONDecodeError:
            welcome = None

    autorole = None
    if autorole_raw:
        try:
            autorole = json.loads(autorole_raw)
        except json.JSONDecodeError:
            autorole = None

    return {"guild_id": guild_id, "welcome": welcome, "autorole": autorole}


@router.post("/guilds/{guild_id}/automation/test-welcome")
async def send_test_welcome(guild_id: str) -> dict[str, Any]:
    """Post the configured welcome message with sample values right now."""

    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="DISCORD_BOT_TOKEN is not configured in Norgoth/.env.",
        )

    redis_client = await get_redis()

    try:
        config = await read_stored_config(redis_client, guild_id)
        raw_resources = await redis_client.get(guild_resources_key(guild_id))
    finally:
        await redis_client.aclose()

    if not config.welcome_channel_id:
        raise HTTPException(
            status_code=400,
            detail="No welcome channel is configured. Save a channel first.",
        )

    guild_name = "your server"
    member_count = "1"

    if raw_resources:
        try:
            resources = json.loads(raw_resources)
            guild_name = str(resources.get("guild_name") or guild_name)
            member_count = str(resources.get("member_count") or member_count)
        except json.JSONDecodeError:
            pass

    rendered = (
        (config.welcome_message or "Welcome to {server}, {user}!")
        .replace("{user}", "@TestMember")
        .replace("{username}", "TestMember")
        .replace("{server}", guild_name)
        .replace("{member_count}", member_count)
        .replace("{inviter}", "TestInviter")
        .replace("{inviter_count}", "1")
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                f"{DISCORD_API_BASE_URL}/channels/{config.welcome_channel_id}/messages",
                headers={"Authorization": f"Bot {bot_token}"},
                json={"content": f"[Test] {rendered}"[:2000]},
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach Discord: {error}",
            ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Discord rejected the test message "
                f"(HTTP {response.status_code}): {response.text[:200]}"
            ),
        )

    return {
        "ok": True,
        "channel_id": config.welcome_channel_id,
        "rendered_message": rendered,
        "sent_at": now_iso(),
    }


@router.post("/guilds/{guild_id}/automation/test-leave")
async def send_test_leave(guild_id: str) -> dict[str, Any]:
    """Post the configured leave message with sample values right now."""

    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="DISCORD_BOT_TOKEN is not configured in Norgoth/.env.",
        )

    redis_client = await get_redis()

    try:
        config = await read_stored_config(redis_client, guild_id)
        raw_resources = await redis_client.get(guild_resources_key(guild_id))
    finally:
        await redis_client.aclose()

    # Leave messages fall back to the welcome channel when no dedicated leave
    # channel is configured, mirroring the bot's runtime behaviour.
    target_channel_id = config.leave_channel_id or config.welcome_channel_id

    if not target_channel_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "No leave or welcome channel is configured. Save a channel "
                "first."
            ),
        )

    guild_name = "your server"
    member_count = "1"

    if raw_resources:
        try:
            resources = json.loads(raw_resources)
            guild_name = str(resources.get("guild_name") or guild_name)
            member_count = str(resources.get("member_count") or member_count)
        except json.JSONDecodeError:
            pass

    rendered = (
        (config.leave_message or "{username} has left {server}.")
        .replace("{user}", "@TestMember")
        .replace("{username}", "TestMember")
        .replace("{server}", guild_name)
        .replace("{member_count}", member_count)
        .replace("{inviter}", "TestInviter")
        .replace("{inviter_count}", "1")
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                f"{DISCORD_API_BASE_URL}/channels/{target_channel_id}/messages",
                headers={"Authorization": f"Bot {bot_token}"},
                json={"content": f"[Test] {rendered}"[:2000]},
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach Discord: {error}",
            ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Discord rejected the test message "
                f"(HTTP {response.status_code}): {response.text[:200]}"
            ),
        )

    return {
        "ok": True,
        "channel_id": target_channel_id,
        "rendered_message": rendered,
        "sent_at": now_iso(),
    }
