"""Authentication dependencies for operator sessions and guild authz."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.security.discord_permissions import can_manage_guild
from app.security.session import COOKIE_NAME, OperatorSession, SessionService
from app.api.v1.dependencies import (
    HTTPClientDependency,
    _require_discord_oauth_settings,
)
from app.api.v1.discord_http import http_detail
from app.api.v1.operator_discord import fetch_operator_guilds
from app.integrations.discord.oauth import DiscordOAuthClient

logger = logging.getLogger(__name__)


def get_session_service() -> SessionService:
    return SessionService()


async def get_optional_operator_session(
    norgoth_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    sessions: Annotated[SessionService, Depends(get_session_service)] = None,  # type: ignore[assignment]
) -> OperatorSession | None:
    if sessions is None:
        sessions = SessionService()
    if not norgoth_session:
        return None
    return await sessions.get_session(norgoth_session)


async def require_operator_session(
    session: Annotated[
        OperatorSession | None, Depends(get_optional_operator_session)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorSession:
    if session is not None:
        return session
    if not settings.auth_enforced:
        # Dev convenience: anonymous operator stub when auth is soft.
        return OperatorSession(
            session_id="dev",
            user_id="0",
            username="dev",
            global_name="Developer",
            avatar=None,
            created_at=0,
            expires_at=2**31 - 1,
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=http_detail(
            "authentication_required",
            "Authentication required.",
        ),
    )


OperatorSessionDependency = Annotated[
    OperatorSession,
    Depends(require_operator_session),
]

OptionalOperatorSessionDependency = Annotated[
    OperatorSession | None,
    Depends(get_optional_operator_session),
]


async def require_guild_manager(
    guild_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorSession:
    """Verify the operator may manage the requested guild."""

    if not settings.auth_enforced and session.user_id == "0":
        return session

    # Build the OAuth client lazily so the dev-bypass path never requires
    # Discord OAuth configuration (which would otherwise raise 503 eagerly
    # when this guard is resolved).
    client_id, client_secret, redirect_uri = _require_discord_oauth_settings(settings)
    oauth_client = DiscordOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        http_client=http_client,
    )

    guilds = await fetch_operator_guilds(
        sessions=sessions,
        oauth_client=oauth_client,
        user_id=session.user_id,
        route="require_guild_manager",
    )

    match = next((g for g in guilds if g.id == guild_id), None)
    if match is None or not can_manage_guild(
        owner=match.owner, permissions=match.permissions
    ):
        logger.warning(
            "guild_permission_denied user_id=%s guild_id=%s",
            session.user_id,
            guild_id,
        )
        raise HTTPException(
            status_code=403,
            detail=http_detail(
                "guild_permission_denied",
                "You do not have permission to manage this guild.",
            ),
        )
    return session


def guild_manager_dependency(guild_id_param: str = "guild_id"):
    """Factory for path-param guild authorization dependencies."""

    async def _dep(
        request: Request,
        session: OperatorSessionDependency,
        http_client: HTTPClientDependency,
        sessions: Annotated[SessionService, Depends(get_session_service)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> OperatorSession:
        guild_id = request.path_params.get(guild_id_param) or request.path_params.get(
            "discord_guild_id"
        )
        if not guild_id:
            raise HTTPException(status_code=400, detail="Missing guild id.")
        return await require_guild_manager(
            str(guild_id),
            session,
            http_client,
            sessions,
            settings,
        )

    return _dep


async def require_platform_admin(
    session: OperatorSessionDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorSession:
    """Restrict global ops (queue pause/rehydrate) to an explicit allowlist."""

    if not settings.auth_enforced and session.user_id == "0":
        return session
    allowed = set(settings.platform_admin_ids)
    if session.user_id not in allowed:
        logger.warning(
            "platform_admin_required user_id=%s",
            session.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=http_detail(
                "platform_admin_required",
                "This operation is restricted to platform administrators.",
            ),
        )
    return session


async def operator_manageable_guild_ids(
    session: OperatorSession,
    http_client: HTTPClientDependency,
    sessions: SessionService,
    settings: Settings,
) -> set[str]:
    """Return Discord guild IDs the operator may manage."""

    if not settings.auth_enforced and session.user_id == "0":
        return {"*"}

    client_id, client_secret, redirect_uri = _require_discord_oauth_settings(settings)
    oauth_client = DiscordOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        http_client=http_client,
    )
    guilds = await fetch_operator_guilds(
        sessions=sessions,
        oauth_client=oauth_client,
        user_id=session.user_id,
        route="operator_manageable_guild_ids",
    )
    return {
        guild.id
        for guild in guilds
        if can_manage_guild(owner=guild.owner, permissions=guild.permissions)
    }
