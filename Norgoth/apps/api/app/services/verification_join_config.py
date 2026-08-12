"""Internal bot snapshot for join-time Unverified role assignment."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from app.db.session import get_session_factory
from app.db.url import DatabaseConfigurationError
from app.models.guild import Guild
from app.repositories.configuration_repository import ConfigurationRepository
from app.services.campaign_store import get_redis
from app.services.configuration_service import ConfigurationService
from app.services.verification_setup import (
    derive_verification_setup_state,
    has_required_bindings,
)

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "norgoth:verification:join:"
CACHE_TTL_SECONDS = 300


def _cache_key(discord_guild_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}{discord_guild_id}"


async def invalidate_verification_join_cache(discord_guild_id: str) -> None:
    try:
        redis_client = await get_redis()
        try:
            await redis_client.delete(_cache_key(discord_guild_id))
        finally:
            await redis_client.aclose()
    except Exception:
        logger.debug("Could not invalidate verification join cache", exc_info=True)


async def load_verification_join_config(discord_guild_id: str) -> dict[str, Any]:
    """Return join-time verification snapshot from Redis/Postgres."""

    cached = await _read_cache(discord_guild_id)
    if cached is not None:
        return cached

    payload = await _load_from_postgres(discord_guild_id)
    await _write_cache(discord_guild_id, payload)
    return payload


async def _read_cache(discord_guild_id: str) -> dict[str, Any] | None:
    try:
        redis_client = await get_redis()
        try:
            raw = await redis_client.get(_cache_key(discord_guild_id))
        finally:
            await redis_client.aclose()
    except Exception:
        return None
    if not raw:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


async def _write_cache(discord_guild_id: str, payload: dict[str, Any]) -> None:
    try:
        redis_client = await get_redis()
        try:
            await redis_client.set(
                _cache_key(discord_guild_id),
                json.dumps(payload, separators=(",", ":")),
                ex=CACHE_TTL_SECONDS,
            )
        finally:
            await redis_client.aclose()
    except Exception:
        logger.debug("Could not write verification join cache", exc_info=True)


async def _load_from_postgres(discord_guild_id: str) -> dict[str, Any]:
    empty = {
        "enabled": False,
        "active": False,
        "unverified_role_id": "",
        "setup_state": "not_configured",
        "has_required_bindings": False,
    }
    try:
        factory = get_session_factory()
    except DatabaseConfigurationError:
        return empty
    except Exception:
        logger.exception("Could not open DB for verification join config")
        return empty

    try:
        async with factory() as session:
            guild = (
                await session.execute(
                    select(Guild).where(Guild.discord_guild_id == str(discord_guild_id))
                )
            ).scalar_one_or_none()
            if guild is None:
                return empty

            service = ConfigurationService(ConfigurationRepository(session))
            view = await service.get_by_guild_id(guild.id)
            if view is None:
                return empty

            status = derive_verification_setup_state(view)
            return {
                "enabled": bool(view.enabled),
                "active": status.state == "active",
                "unverified_role_id": view.unverified_role_id,
                "setup_state": status.state,
                "has_required_bindings": has_required_bindings(view),
            }
    except Exception:
        logger.exception(
            "Failed loading verification join config for guild %s",
            discord_guild_id,
        )
        return empty
