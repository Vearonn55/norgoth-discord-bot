"""Shared Discord guild fetch for operator session routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.v1.discord_http import http_detail, raise_discord_oauth_http_error
from app.integrations.discord.oauth import (
    DiscordOAuthClient,
    DiscordOAuthError,
    DiscordOAuthGuild,
)
from app.security.session import SessionService


async def fetch_operator_guilds(
    *,
    sessions: SessionService,
    oauth_client: DiscordOAuthClient,
    user_id: str,
    request: Request | None = None,
    route: str = "unknown",
) -> list[DiscordOAuthGuild]:
    """Load the operator's Discord guilds, refreshing the OAuth token once if needed."""

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
