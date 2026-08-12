"""Shared Discord guild fetch for operator session routes."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, Request

from app.api.v1.discord_http import http_detail, raise_discord_oauth_http_error
from app.integrations.discord.oauth import (
    DiscordOAuthClient,
    DiscordOAuthError,
    DiscordOAuthGuild,
)
from app.security.session import SessionService
from app.services.campaign_store import get_redis

logger = logging.getLogger(__name__)

# Short TTL collapses concurrent post-OAuth fan-out (server selector +
# guild-store + require_guild_manager) into one Discord /users/@me/guilds hit.
OPERATOR_GUILDS_CACHE_TTL_SECONDS = 45
OPERATOR_GUILDS_LOCK_TTL_SECONDS = 10
OPERATOR_GUILDS_LOCK_WAIT_SECONDS = 1.5
OPERATOR_GUILDS_LOCK_POLL_SECONDS = 0.1

# In-process singleflight so one uvicorn worker does not stampede Discord.
_inflight_guild_fetches: dict[str, asyncio.Task[list[DiscordOAuthGuild]]] = {}
_inflight_guard = asyncio.Lock()


def operator_guilds_cache_key(user_id: str) -> str:
    return f"norgoth:operator:{user_id}:guilds"


def operator_guilds_lock_key(user_id: str) -> str:
    return f"norgoth:operator:{user_id}:guilds:lock"


def _serialize_guilds(guilds: list[DiscordOAuthGuild]) -> str:
    return json.dumps([asdict(guild) for guild in guilds], separators=(",", ":"))


def _deserialize_guilds(raw: str | bytes | None) -> list[DiscordOAuthGuild] | None:
    if not raw:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None

    guilds: list[DiscordOAuthGuild] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        guild_id = item.get("id")
        name = item.get("name")
        permissions = item.get("permissions")
        if not isinstance(guild_id, str) or not isinstance(name, str):
            continue
        if not isinstance(permissions, str):
            permissions = str(permissions) if permissions is not None else "0"
        icon = item.get("icon")
        guilds.append(
            DiscordOAuthGuild(
                id=guild_id,
                name=name,
                owner=bool(item.get("owner")),
                permissions=permissions,
                icon=icon if isinstance(icon, str) else None,
            )
        )
    return guilds


async def invalidate_operator_guilds_cache(
    user_id: str,
    *,
    redis_client: Any | None = None,
) -> None:
    """Drop cached operator guilds (call on logout / token clear)."""

    owns_client = redis_client is None
    client = redis_client or await get_redis()
    try:
        await client.delete(operator_guilds_cache_key(user_id))
        await client.delete(operator_guilds_lock_key(user_id))
    finally:
        if owns_client:
            await client.aclose()


async def _read_cached_guilds(user_id: str) -> list[DiscordOAuthGuild] | None:
    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001 - cache must never block Discord fetch
        logger.exception("operator_guilds_cache_connect_failed user_id=%s", user_id)
        return None
    try:
        return _deserialize_guilds(
            await redis_client.get(operator_guilds_cache_key(user_id))
        )
    except Exception:  # noqa: BLE001
        logger.exception("operator_guilds_cache_read_failed user_id=%s", user_id)
        return None
    finally:
        await redis_client.aclose()


async def _write_cached_guilds(user_id: str, guilds: list[DiscordOAuthGuild]) -> None:
    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001
        logger.exception("operator_guilds_cache_connect_failed user_id=%s", user_id)
        return
    try:
        await redis_client.set(
            operator_guilds_cache_key(user_id),
            _serialize_guilds(guilds),
            ex=OPERATOR_GUILDS_CACHE_TTL_SECONDS,
        )
    except Exception:  # noqa: BLE001
        logger.exception("operator_guilds_cache_write_failed user_id=%s", user_id)
    finally:
        await redis_client.aclose()


async def _acquire_guilds_lock(user_id: str) -> bool:
    """Return True when this caller should hit Discord (lock acquired or Redis down)."""

    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001
        logger.exception("operator_guilds_lock_connect_failed user_id=%s", user_id)
        return True
    try:
        acquired = await redis_client.set(
            operator_guilds_lock_key(user_id),
            "1",
            nx=True,
            ex=OPERATOR_GUILDS_LOCK_TTL_SECONDS,
        )
        return bool(acquired)
    except Exception:  # noqa: BLE001
        logger.exception("operator_guilds_lock_failed user_id=%s", user_id)
        return True
    finally:
        await redis_client.aclose()


async def _fetch_guilds_from_discord(
    *,
    sessions: SessionService,
    oauth_client: DiscordOAuthClient,
    user_id: str,
    request: Request | None,
    route: str,
) -> list[DiscordOAuthGuild]:
    token = await sessions.get_valid_access_token(
        user_id,
        oauth_client=oauth_client,
    )
    if not token:
        raise HTTPException(
            status_code=401,
            detail=http_detail(
                "discord_token_invalid",
                "Session token expired. Please reconnect Discord.",
            ),
        )

    try:
        return await oauth_client.get_current_user_guilds(access_token=token)
    except DiscordOAuthError as error:
        if error.http_status in {401, 403}:
            refreshed = await sessions.get_valid_access_token(
                user_id,
                oauth_client=oauth_client,
                force_refresh=True,
            )
            if refreshed:
                try:
                    return await oauth_client.get_current_user_guilds(
                        access_token=refreshed
                    )
                except DiscordOAuthError as retry_error:
                    if retry_error.http_status in {401, 403}:
                        await sessions.clear_oauth_tokens(user_id)
                    raise_discord_oauth_http_error(
                        retry_error,
                        request=request,
                        route=route,
                    )
            await sessions.clear_oauth_tokens(user_id)
        raise_discord_oauth_http_error(error, request=request, route=route)
        raise  # pragma: no cover — raise_discord_oauth_http_error always raises


async def _fetch_with_redis_singleflight(
    *,
    sessions: SessionService,
    oauth_client: DiscordOAuthClient,
    user_id: str,
    request: Request | None,
    route: str,
) -> list[DiscordOAuthGuild]:
    cached = await _read_cached_guilds(user_id)
    if cached is not None:
        return cached

    acquired = await _acquire_guilds_lock(user_id)
    if not acquired:
        waited = 0.0
        while waited < OPERATOR_GUILDS_LOCK_WAIT_SECONDS:
            await asyncio.sleep(OPERATOR_GUILDS_LOCK_POLL_SECONDS)
            waited += OPERATOR_GUILDS_LOCK_POLL_SECONDS
            cached = await _read_cached_guilds(user_id)
            if cached is not None:
                return cached
        logger.info(
            "operator_guilds_lock_wait_exhausted user_id=%s route=%s",
            user_id,
            route,
        )

    guilds = await _fetch_guilds_from_discord(
        sessions=sessions,
        oauth_client=oauth_client,
        user_id=user_id,
        request=request,
        route=route,
    )
    await _write_cached_guilds(user_id, guilds)
    return guilds


async def fetch_operator_guilds(
    *,
    sessions: SessionService,
    oauth_client: DiscordOAuthClient,
    user_id: str,
    request: Request | None = None,
    route: str = "unknown",
) -> list[DiscordOAuthGuild]:
    """Load the operator's Discord guilds, refreshing the OAuth token once if needed.

    Concurrent callers for the same user share one Discord request via an
    in-process task plus a short Redis cache/lock (cross-worker).
    """

    cached = await _read_cached_guilds(user_id)
    if cached is not None:
        return cached

    async with _inflight_guard:
        existing = _inflight_guild_fetches.get(user_id)
        if existing is None:

            async def _runner() -> list[DiscordOAuthGuild]:
                try:
                    return await _fetch_with_redis_singleflight(
                        sessions=sessions,
                        oauth_client=oauth_client,
                        user_id=user_id,
                        request=request,
                        route=route,
                    )
                finally:
                    async with _inflight_guard:
                        _inflight_guild_fetches.pop(user_id, None)

            existing = asyncio.create_task(_runner())
            _inflight_guild_fetches[user_id] = existing

    return await existing
