"""Operator session endpoints."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.v1.dependencies import (
    DiscordOAuthClientDependency,
    SettingsDependency,
)
from app.api.v1.dependencies_auth import (
    OptionalOperatorSessionDependency,
    OperatorSessionDependency,
    get_session_service,
)
from app.api.v1.discord_http import http_detail
from app.api.v1.operator_discord import fetch_operator_guilds
from app.integrations.discord.cdn import discord_icon_url
from app.security.discord_permissions import can_manage_guild, guild_role_label
from app.security.session import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    OperatorSession,
    SessionService,
)
from app.services.campaign_store import get_redis
from app.services.guild_setup_state import (
    derive_setup_state,
    lookup_configured_guild_ids,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=8, max_length=200)


@router.post("/exchange")
async def exchange_session(
    body: ExchangeRequest,
    response: Response,
    settings: SettingsDependency,
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> dict[str, Any]:
    session = await sessions.exchange_code(body.code)
    if session is None:
        raise HTTPException(
            status_code=400,
            detail=http_detail(
                "exchange_code_invalid",
                "Invalid or expired exchange code.",
            ),
        )

    secure = settings.environment == "production"
    response.set_cookie(
        key=COOKIE_NAME,
        value=session.session_id,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return {"user": session.to_public_dict()}


@router.get("/me")
async def current_session(
    session: OptionalOperatorSessionDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    if session is not None:
        return {"authenticated": True, "user": session.to_public_dict()}
    if not settings.auth_enforced:
        stub = OperatorSession(
            session_id="dev",
            user_id="0",
            username="dev",
            global_name="Developer",
            avatar=None,
            created_at=0,
            expires_at=2**31 - 1,
        )
        return {"authenticated": True, "user": stub.to_public_dict()}
    return {"authenticated": False, "user": None}


@router.post("/logout")
async def logout(
    response: Response,
    sessions: Annotated[SessionService, Depends(get_session_service)],
    norgoth_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> dict[str, str]:
    if norgoth_session:
        await sessions.delete_session(norgoth_session)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/servers")
async def list_manageable_servers(
    request: Request,
    session: OperatorSessionDependency,
    oauth_client: DiscordOAuthClientDependency,
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: SettingsDependency,
) -> dict[str, Any]:
    redis_client = await get_redis()
    try:
        bot_guild_ids: set[str] = set()
        bot_icon_by_id: dict[str, str | None] = {}
        bot_guilds: list[dict[str, Any]] = []
        status_raw = await redis_client.get("norgoth:bot:status")
        if status_raw:
            try:
                if isinstance(status_raw, bytes):
                    status_raw = status_raw.decode("utf-8")
                status = json.loads(status_raw)
                for guild in status.get("guilds") or []:
                    if isinstance(guild, dict) and guild.get("id"):
                        gid = str(guild["id"])
                        bot_guild_ids.add(gid)
                        icon_hash = guild.get("icon")
                        normalized_icon = str(icon_hash) if isinstance(icon_hash, str) else None
                        bot_icon_by_id[gid] = normalized_icon
                        bot_guilds.append(
                            {
                                "id": gid,
                                "name": str(guild.get("name") or gid),
                                "icon": normalized_icon,
                                "icon_url": discord_icon_url(gid, normalized_icon),
                                "owner": False,
                                "permissions": "0",
                                "role_label": guild_role_label(
                                    owner=False,
                                    permissions="0",
                                ),
                                "bot_installed": True,
                                "manageable": True,
                                "setup_state": "not_configured",
                            }
                        )
            except json.JSONDecodeError:
                pass
        if not bot_guild_ids:
            keys = await redis_client.keys("norgoth:guild:*:resources")
            for key in keys:
                key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
                parts = key_str.split(":")
                if len(parts) >= 3:
                    bot_guild_ids.add(parts[2])
    finally:
        await redis_client.aclose()

    async def _bot_only_servers() -> dict[str, Any]:
        configured = await lookup_configured_guild_ids(bot_guild_ids)
        _apply_setup_state(bot_guilds, bot_guild_ids, configured)
        return {"servers": bot_guilds}

    if not settings.auth_enforced and session.user_id == "0":
        return await _bot_only_servers()

    if not settings.auth_enforced:
        token = await sessions.get_access_token(session.user_id)
        if not token:
            return await _bot_only_servers()

    user_guilds = await fetch_operator_guilds(
        sessions=sessions,
        oauth_client=oauth_client,
        user_id=session.user_id,
        request=request,
        route="/sessions/servers",
    )

    eligible_ids: set[str] = set()
    pending: list[tuple[Any, bool]] = []
    for guild in user_guilds:
        if not can_manage_guild(owner=guild.owner, permissions=guild.permissions):
            continue
        eligible_ids.add(guild.id)
        pending.append((guild, guild.id in bot_guild_ids))

    configured_ids = await lookup_configured_guild_ids(eligible_ids | bot_guild_ids)

    servers = []
    for guild, bot_installed in pending:
        icon_hash = guild.icon or bot_icon_by_id.get(guild.id)
        servers.append(
            {
                "id": guild.id,
                "name": guild.name,
                "icon": icon_hash,
                "icon_url": discord_icon_url(guild.id, icon_hash),
                "owner": guild.owner,
                "permissions": guild.permissions,
                "role_label": guild_role_label(
                    owner=guild.owner,
                    permissions=guild.permissions,
                ),
                "bot_installed": bot_installed,
                "manageable": True,
                "setup_state": derive_setup_state(
                    bot_installed=bot_installed,
                    configured=guild.id in configured_ids,
                ),
            }
        )

    state_rank = {"configured": 0, "not_configured": 1, "not_installed": 2}
    servers.sort(
        key=lambda item: (
            state_rank.get(item["setup_state"], 9),
            item["name"].lower(),
        )
    )
    return {"servers": servers}


def _apply_setup_state(
    bot_guilds: list[dict[str, Any]],
    bot_guild_ids: set[str],
    configured_ids: set[str],
) -> None:
    for item in bot_guilds:
        item["setup_state"] = derive_setup_state(
            bot_installed=item["id"] in bot_guild_ids,
            configured=item["id"] in configured_ids,
        )
