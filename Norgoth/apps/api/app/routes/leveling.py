"""Leveling configuration and leaderboard."""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso

router = APIRouter(
    tags=["Leveling"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"


def leveling_config_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:leveling:config"


def xp_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:xp"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


def xp_for_level(level: int) -> int:
    total = 0
    for step in range(level):
        total += 5 * step**2 + 50 * step + 100
    return total


def level_from_xp(xp: int) -> int:
    level = 0
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


class RewardRole(BaseModel):
    level: int = Field(ge=1, le=1000)
    role_id: str = Field(pattern=SNOWFLAKE_PATTERN)


class LevelingConfig(BaseModel):
    announce_mode: Literal["current", "channel", "off"] = "current"
    announce_channel_id: Optional[str] = Field(
        default=None, pattern=SNOWFLAKE_PATTERN
    )
    # Base XP awarded per eligible message (before the multiplier). Bounded to
    # keep progression balanced and prevent runaway values.
    xp_per_message: int = Field(default=15, ge=1, le=100)
    # Reward magnitude multiplier. Scales the base XP only; it does NOT relax
    # the cooldown / anti-spam eligibility gate enforced by the bot.
    xp_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    # Level-up messages are always delivered as an embed. This body is the
    # single source of truth for the embed description.
    level_up_message: str = Field(
        default="🎉 {user} reached level **{level}**!",
        max_length=2000,
    )
    level_up_embed: dict[str, Any] = Field(default_factory=dict)
    reward_roles: list[RewardRole] = Field(default_factory=list, max_length=25)


@router.get("/guilds/{guild_id}/leveling/config")
async def get_leveling_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(leveling_config_key(guild_id))
    finally:
        await redis_client.aclose()

    defaults = LevelingConfig().model_dump()

    if not raw:
        return defaults

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return defaults

    if not isinstance(stored, dict):
        return defaults

    return {**defaults, **{k: v for k, v in stored.items() if k in defaults}}


@router.put("/guilds/{guild_id}/leveling/config")
async def update_leveling_config(
    guild_id: str,
    config: LevelingConfig,
) -> dict[str, Any]:
    payload = config.model_dump()
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await redis_client.set(
            leveling_config_key(guild_id),
            json.dumps(payload),
        )
    finally:
        await redis_client.aclose()

    return payload


@router.get("/guilds/{guild_id}/leveling/leaderboard")
async def get_leaderboard(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        entries = await redis_client.zrevrange(
            xp_key(guild_id),
            0,
            limit - 1,
            withscores=True,
        )
        raw_members = await redis_client.get(guild_members_key(guild_id))
    finally:
        await redis_client.aclose()

    names: dict[str, str] = {}

    if raw_members:
        try:
            snapshot = json.loads(raw_members)
            for member in snapshot.get("members", []):
                names[str(member.get("id"))] = str(
                    member.get("display_name") or member.get("name") or ""
                )
        except (json.JSONDecodeError, AttributeError):
            pass

    leaderboard: list[dict[str, Any]] = []

    for index, (user_id, score) in enumerate(entries, start=1):
        xp = int(score)
        leaderboard.append(
            {
                "rank": index,
                "user_id": str(user_id),
                "name": names.get(str(user_id)) or f"User {user_id}",
                "xp": xp,
                "level": level_from_xp(xp),
            }
        )

    return leaderboard
