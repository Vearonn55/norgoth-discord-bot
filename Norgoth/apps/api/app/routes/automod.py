"""Per-guild rule-based auto-moderation configuration."""

from __future__ import annotations

import json
from typing import Any, List, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

router = APIRouter(
    tags=["AutoMod"],
    dependencies=[Depends(guild_manager_dependency())],
)

AutomodAction = Literal["delete", "warn", "timeout"]


def automod_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:automod"


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
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await save_config(guild_id, "automod", payload, enabled=bool(payload.get("enabled", False)))
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}
