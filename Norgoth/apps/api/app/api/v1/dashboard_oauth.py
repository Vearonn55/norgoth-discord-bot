"""Operator dashboard Discord OAuth (separate from member verification)."""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import (
    DiscordOAuthClientDependency,
    DiscordOAuthStateServiceDependency,
    HTTPClientDependency,
    SettingsDependency,
    _require_discord_oauth_settings,
)
from app.api.v1.dependencies_auth import (
    OptionalOperatorSessionDependency,
    get_session_service,
)
from app.integrations.discord.oauth import DiscordOAuthClient, DiscordOAuthError
from app.security.discord_permissions import (
    build_bot_invite_url,
    can_manage_guild,
)
from app.security.oauth_state import DiscordOAuthStateService, InvalidOAuthStateError
from app.security.session import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth/discord", tags=["dashboard-oauth"])


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
async def bot_invite(
    settings: SettingsDependency,
    session: OptionalOperatorSessionDependency,
    http_client: HTTPClientDependency,
    guild_id: Annotated[str | None, Query(pattern=r"^[0-9]{5,25}$")] = None,
) -> RedirectResponse:
    """Redirect to Discord Guild Install (bot + applications.commands).

    Optional ``guild_id`` preselects that server. When provided, the caller
    must be an authenticated operator who can manage that guild.
    """

    app_id = settings.discord_application_id or settings.discord_client_id
    if not app_id:
        raise HTTPException(
            status_code=503,
            detail="Discord application ID is not configured.",
        )

    resolved_guild_id: str | None = None
    if guild_id:
        if session is None:
            if settings.auth_enforced:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required.",
                )
            # Soft-auth local/dev: allow guild preselect without Discord
            # membership verification (no operator token available).
            resolved_guild_id = guild_id
        elif not settings.auth_enforced and session.user_id == "0":
            resolved_guild_id = guild_id
        else:
            sessions = get_session_service()
            token = await sessions.get_access_token(session.user_id)
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session token expired. Please sign in again.",
                )
            client_id, client_secret, redirect_uri = _require_discord_oauth_settings(
                settings
            )
            oauth_client = DiscordOAuthClient(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                http_client=http_client,
            )
            try:
                user_guilds = await oauth_client.get_current_user_guilds(
                    access_token=token
                )
            except DiscordOAuthError as error:
                raise HTTPException(
                    status_code=502,
                    detail="Could not verify guild permissions.",
                ) from error

            match = next((g for g in user_guilds if g.id == guild_id), None)
            if match is None or not can_manage_guild(
                owner=match.owner,
                permissions=match.permissions,
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to add NorBot to this guild.",
                )
            resolved_guild_id = guild_id

    url = build_bot_invite_url(client_id=app_id, guild_id=resolved_guild_id)
    return RedirectResponse(
        url=url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
