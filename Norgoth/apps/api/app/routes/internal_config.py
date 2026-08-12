"""Internal bot endpoints to rehydrate Redis config snapshots from Postgres."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path

from app.core.config import get_settings
from app.services.campaign_store import get_redis
from app.services.feature_config_store import FEATURE_REGISTRY, read_through
from app.services.verification_join_config import load_verification_join_config

SNOWFLAKE = r"^[0-9]{5,25}$"


async def require_bot_token(
    x_norgoth_bot_token: str | None = Header(default=None),
) -> None:
    expected = get_settings().discord_bot_token
    if not expected or x_norgoth_bot_token != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token.")


router = APIRouter(
    prefix="/internal/config",
    tags=["Internal Config"],
    dependencies=[Depends(require_bot_token)],
)


@router.get("/verification/{guild_id}")
async def hydrate_verification_join_config(
    guild_id: str = Path(pattern=SNOWFLAKE),
) -> dict[str, Any]:
    """Return join-time verification snapshot for the Gateway bot.

    Postgres remains the source of truth; Redis caches a short-lived snapshot.
    """

    payload = await load_verification_join_config(guild_id)
    return {"guild_id": guild_id, "config": payload}


@router.get("/{guild_id}/{feature_key}")
async def hydrate_feature_config(
    guild_id: str = Path(pattern=SNOWFLAKE),
    feature_key: str = Path(min_length=1, max_length=64),
) -> dict[str, Any]:
    """Return durable feature config and rewrite the Redis snapshot on a miss.

    The bot stays DB-free: on a Redis cache miss it calls this endpoint so
    Postgres remains the source of truth while Redis stays a hot snapshot.
    """

    if feature_key not in FEATURE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown feature: {feature_key}")

    redis_client = await get_redis()
    try:
        payload = await read_through(guild_id, feature_key, redis_client)
    finally:
        await redis_client.aclose()

    return {
        "guild_id": guild_id,
        "feature_key": feature_key,
        "config": payload if isinstance(payload, dict) else {},
    }
