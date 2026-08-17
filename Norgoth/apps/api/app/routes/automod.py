"""Per-guild rule-based auto-moderation configuration."""

from __future__ import annotations

import json
from typing import Any, List, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.api.v1.discord_http import http_detail
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

router = APIRouter(
    tags=["AutoMod"],
    dependencies=[Depends(guild_manager_dependency())],
)

AutomodAction = Literal["delete", "warn", "timeout"]

_ID_LIST_KEYS = (
    "exempt_channel_ids",
    "exempt_role_ids",
    "image_only_channel_ids",
    "link_only_channel_ids",
)


def automod_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:automod"


def snowflake_list(values: list[str] | None) -> list[str]:
    """Keep unique Discord snowflakes in first-seen order."""

    seen: dict[str, None] = {}
    for value in values or []:
        if isinstance(value, str) and value.isdigit() and 5 <= len(value) <= 25:
            seen.setdefault(value, None)
    return list(seen)


def sanitize_automod_id_lists(payload: dict[str, Any]) -> dict[str, Any]:
    for key in _ID_LIST_KEYS:
        payload[key] = snowflake_list(payload.get(key) or [])
    return payload


def validate_format_channel_rules(payload: dict[str, Any]) -> None:
    """Reject unusable enabled states and Image Only / Link Only overlap."""

    image_ids = list(payload.get("image_only_channel_ids") or [])
    link_ids = list(payload.get("link_only_channel_ids") or [])

    if payload.get("image_only_enabled") and not image_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=http_detail(
                "automod_image_only_channels_required",
                "Enable Image Only Channel only after selecting at least one channel.",
            ),
        )

    if payload.get("link_only_enabled") and not link_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=http_detail(
                "automod_link_only_channels_required",
                "Enable Link Only Channel only after selecting at least one channel.",
            ),
        )

    overlap = [channel_id for channel_id in image_ids if channel_id in set(link_ids)]
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                **http_detail(
                    "automod_channel_rule_conflict",
                    "A channel cannot be both Image Only and Link Only.",
                ),
                "channel_ids": overlap,
            },
        )


class ModerationScope(BaseModel):
    """Where auto-moderation applies. Defaults to everywhere for back-compat."""

    text: bool = True
    threads: bool = True
    voice_text: bool = True


class AutomodConfig(BaseModel):
    enabled: bool = False

    # Which channel contexts auto-moderation evaluates.
    moderation_scope: ModerationScope = Field(default_factory=ModerationScope)

    # Prohibited-word filtering can be toggled without clearing the word list.
    # Defaults to True so existing configurations (with words already set)
    # continue to filter after upgrading.
    words_enabled: bool = True
    prohibited_words: List[str] = Field(default_factory=list, max_length=200)
    word_action: AutomodAction = "delete"

    spam_enabled: bool = True
    spam_max_messages: int = Field(default=6, ge=2, le=30)
    spam_interval_seconds: int = Field(default=8, ge=2, le=120)
    spam_action: AutomodAction = "timeout"

    duplicate_enabled: bool = True
    duplicate_threshold: int = Field(default=3, ge=2, le=10)

    block_invites: bool = False
    invite_action: AutomodAction = "delete"

    mass_mention_enabled: bool = True
    mass_mention_threshold: int = Field(default=6, ge=2, le=30)
    mass_mention_action: AutomodAction = "delete"

    timeout_minutes: int = Field(default=10, ge=1, le=40320)

    exempt_manage_messages: bool = True
    exempt_channel_ids: List[str] = Field(default_factory=list, max_length=50)
    exempt_role_ids: List[str] = Field(default_factory=list, max_length=50)

    image_only_enabled: bool = False
    image_only_channel_ids: List[str] = Field(default_factory=list, max_length=50)
    image_only_action: AutomodAction = "delete"

    link_only_enabled: bool = False
    link_only_channel_ids: List[str] = Field(default_factory=list, max_length=50)
    link_only_action: AutomodAction = "delete"


@router.get("/guilds/{guild_id}/automod")
async def get_automod_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await read_raw(guild_id, "automod", redis_client)
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

    config = AutomodConfig(**{
        key: value
        for key, value in stored.items()
        if key in AutomodConfig.model_fields
    })

    return {"guild_id": guild_id, **config.model_dump()}


@router.put("/guilds/{guild_id}/automod")
async def update_automod_config(
    guild_id: str,
    config: AutomodConfig,
) -> dict[str, Any]:
    payload = config.model_dump()
    payload["prohibited_words"] = [
        word.strip() for word in payload["prohibited_words"] if word.strip()
    ]
    sanitize_automod_id_lists(payload)
    validate_format_channel_rules(payload)
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await save_config(guild_id, "automod", payload, enabled=bool(payload.get("enabled", False)))
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}
