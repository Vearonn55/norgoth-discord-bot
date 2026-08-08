"""Operator session endpoints."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
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
from app.integrations.discord.oauth import DiscordOAuthError
from app.security.discord_permissions import can_manage_guild
from app.security.session import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    OperatorSession,
    SessionService,
)
from app.services.campaign_store import get_redis

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
        raise HTTPException(status_code=400, detail="Invalid or expired exchange code.")

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
        # Dev convenience: report an anonymous "Developer" operator so the
        # dashboard behaves as signed-in while Discord login is bypassed.
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
    session: OperatorSessionDependency,
    oauth_client: DiscordOAuthClientDependency,
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: SettingsDependency,
) -> dict[str, Any]:
    redis_client = await get_redis()
    try:
        bot_guild_ids: set[str] = set()
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
                        bot_guilds.append(
                            {
                                "id": gid,
                                "name": str(guild.get("name") or gid),
                                "icon_url": None,
                                "owner": False,
                                "permissions": "0",
                                "bot_installed": True,
                                "manageable": True,
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

    # Soft-auth / missing token: show bot-connected guilds only.
    if not settings.auth_enforced and session.user_id == "0":
        return {"servers": bot_guilds}

    token = await sessions.get_access_token(session.user_id)
    if not token:
        if not settings.auth_enforced:
            return {"servers": bot_guilds}
        raise HTTPException(
            status_code=401,
            detail="Session token expired. Please sign in again.",
        )

    try:
        user_guilds = await oauth_client.get_current_user_guilds(access_token=token)
    except DiscordOAuthError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    servers = []
    for guild in user_guilds:
        if not can_manage_guild(owner=guild.owner, permissions=guild.permissions):
            continue
        bot_installed = guild.id in bot_guild_ids
        icon_url = None
        if guild.icon:
            icon_url = f"https://cdn.discordapp.com/icons/{guild.id}/{guild.icon}.png?size=128"
        servers.append(
            {
                "id": guild.id,
                "name": guild.name,
                "icon_url": icon_url,
                "owner": guild.owner,
                "permissions": guild.permissions,
                "bot_installed": bot_installed,
                "manageable": bot_installed,
            }
        )

    servers.sort(key=lambda item: (not item["bot_installed"], item["name"].lower()))
    return {"servers": servers}
