"""Stream/content notification creator configuration."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso

router = APIRouter(
    tags=["Notifications"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

MAX_CREATORS = 25


def notifications_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:notifications"


class Creator(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    platform: Literal["youtube", "twitch"]
    handle: str = Field(min_length=1, max_length=100)
    display_name: str = Field(default="", max_length=100)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    message: str = Field(default="", max_length=500)

    @field_validator("handle")
    @classmethod
    def clean_handle(cls, value: str) -> str:
        cleaned = value.strip()

        # Accept full URLs and reduce them to the id/login.
        for prefix in (
            "https://www.youtube.com/channel/",
            "https://youtube.com/channel/",
            "https://www.twitch.tv/",
            "https://twitch.tv/",
        ):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break

        return cleaned.strip("/").split("?")[0]


class NotificationsUpdate(BaseModel):
    creators: list[Creator] = Field(default_factory=list, max_length=MAX_CREATORS)


@router.get("/guilds/{guild_id}/notifications")
async def get_notifications_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(notifications_key(guild_id))
    finally:
        await redis_client.aclose()

    creators: list[dict[str, Any]] = []

    if raw:
        try:
            stored = json.loads(raw)
            if isinstance(stored, dict) and isinstance(
                stored.get("creators"), list
            ):
                creators = stored["creators"]
        except json.JSONDecodeError:
            pass

    return {
        "creators": creators,
        "twitch_configured": bool(
            os.getenv("TWITCH_CLIENT_ID", "").strip()
            and os.getenv("TWITCH_CLIENT_SECRET", "").strip()
        ),
    }


@router.put("/guilds/{guild_id}/notifications")
async def update_notifications_config(
    guild_id: str,
    payload: NotificationsUpdate,
) -> dict[str, Any]:
    stored = {
        "creators": [creator.model_dump() for creator in payload.creators],
        "updated_at": now_iso(),
    }

    redis_client = await get_redis()

    try:
        await redis_client.set(notifications_key(guild_id), json.dumps(stored))
    finally:
        await redis_client.aclose()

    return stored
