"""Automatic response rules."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso

router = APIRouter(
    tags=["Auto Responses"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

MAX_RULES = 50


def autoresponses_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:autoresponses"


class AutoResponseRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    trigger: str = Field(min_length=1, max_length=200)
    match_type: Literal["exact", "contains", "starts_with"] = "contains"
    response: str = Field(min_length=1, max_length=1500)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    cooldown_seconds: int = Field(default=10, ge=0, le=3600)


class AutoResponsesUpdate(BaseModel):
    rules: list[AutoResponseRule] = Field(default_factory=list, max_length=MAX_RULES)


@router.get("/guilds/{guild_id}/auto-responses")
async def get_auto_responses(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(autoresponses_key(guild_id))
    finally:
        await redis_client.aclose()

    if not raw:
        return {"rules": []}

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return {"rules": []}

    if not isinstance(stored, dict) or not isinstance(stored.get("rules"), list):
        return {"rules": []}

    return {"rules": stored["rules"]}


@router.put("/guilds/{guild_id}/auto-responses")
async def update_auto_responses(
    guild_id: str,
    payload: AutoResponsesUpdate,
) -> dict[str, Any]:
    stored = {
        "rules": [rule.model_dump() for rule in payload.rules],
        "updated_at": now_iso(),
    }

    redis_client = await get_redis()

    try:
        await redis_client.set(autoresponses_key(guild_id), json.dumps(stored))
    finally:
        await redis_client.aclose()

    return stored
