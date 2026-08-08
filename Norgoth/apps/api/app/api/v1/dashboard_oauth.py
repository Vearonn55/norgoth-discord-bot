"""Operator dashboard Discord OAuth (separate from member verification)."""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import (
    DiscordOAuthClientDependency,
    DiscordOAuthStateServiceDependency,
    SettingsDependency,
    get_http_client,
)
from app.integrations.discord.oauth import DiscordOAuthClient, DiscordOAuthError
from app.security.discord_permissions import BOT_INVITE_PERMISSIONS_MINIMAL
from app.security.oauth_state import DiscordOAuthStateService, InvalidOAuthStateError
from app.security.session import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth/discord", tags=["dashboard-oauth"])

HTTPClientDependency = Annotated[httpx.AsyncClient, Depends(get_http_client)]


@router.get("/dashboard/authorize")
async def authorize_dashboard(
    settings: SettingsDependency,
    http_client: HTTPClientDependency,
    lang: Annotated[str, Query()] = "en",
) -> RedirectResponse:
    resolved_lang = lang if lang in {"en", "tr"} else "en"
    dashboard_base = (settings.dashboard_public_url or "http://127.0.0.1:3000").rstrip(
        "/"
    )

    def fail(reason: str) -> RedirectResponse:
        query = urlencode({"oauth_error": reason})
        return RedirectResponse(
            url=f"{dashboard_base}/{resolved_lang}?{query}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if (
        not settings.discord_client_id
        or not settings.discord_client_secret
        or not settings.discord_redirect_uri
        or not settings.discord_dashboard_redirect_uri
    ):
        return fail("not_configured")

    state_service = DiscordOAuthStateService(secret=settings.discord_client_secret)
    oauth_client = DiscordOAuthClient(
        client_id=settings.discord_client_id,
        client_secret=settings.discord_client_secret,
        redirect_uri=settings.discord_redirect_uri,
        http_client=http_client,
    )

    state = state_service.create(
        discord_guild_id="0",
        purpose="dashboard",
        lang=resolved_lang,
    )
    url = oauth_client.build_authorization_url(
        state=state,
        redirect_uri=settings.discord_dashboard_redirect_uri,
    )
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/dashboard/callback")
async def dashboard_callback(
    request: Request,
    settings: SettingsDependency,
    oauth_client: DiscordOAuthClientDependency,
    state_service: DiscordOAuthStateServiceDependency,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    dashboard_base = (settings.dashboard_public_url or "http://127.0.0.1:3000").rstrip(
        "/"
    )

    def fail(lang: str = "en") -> RedirectResponse:
        return RedirectResponse(
            url=f"{dashboard_base}/{lang}?oauth_error=callback",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if error or not code or not state:
        return fail()

    try:
        oauth_state = state_service.verify(state)
    except InvalidOAuthStateError:
        return fail()

    if oauth_state.purpose != "dashboard":
        return fail(oauth_state.lang)

    if not settings.discord_dashboard_redirect_uri:
        return fail(oauth_state.lang)

    try:
        token = await oauth_client.exchange_code(
            code=code,
            redirect_uri=settings.discord_dashboard_redirect_uri,
        )
        user = await oauth_client.get_current_user(access_token=token.access_token)
    except DiscordOAuthError:
        logger.exception("Dashboard OAuth exchange failed")
        return fail(oauth_state.lang)

    sessions = SessionService()
    _, exchange_code = await sessions.create_session(
        user_id=user.id,
        username=user.username,
        global_name=user.global_name,
        avatar=user.avatar,
        access_token=token.access_token,
        token_expires_in=token.expires_in,
    )

    query = urlencode({"code": exchange_code})
    return RedirectResponse(
        url=f"{dashboard_base}/{oauth_state.lang}/auth/complete?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/bot-invite")
async def bot_invite(settings: SettingsDependency) -> RedirectResponse:
    app_id = settings.discord_application_id or settings.discord_client_id
    if not app_id:
        raise HTTPException(status_code=503, detail="Discord application ID is not configured.")

    query = urlencode(
        {
            "client_id": app_id,
            "permissions": str(BOT_INVITE_PERMISSIONS_MINIMAL),
            "scope": "bot applications.commands",
        }
    )
    return RedirectResponse(
        url=f"https://discord.com/api/oauth2/authorize?{query}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
