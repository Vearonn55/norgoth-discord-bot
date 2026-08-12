"""Tests for Discord permission helpers and session server listing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import sessions as sessions_module
from app.api.v1.dependencies import get_discord_oauth_client
from app.api.v1.dependencies_auth import (
    get_session_service,
    require_operator_session,
)
from app.api.v1.discord_http import raise_discord_oauth_http_error
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.integrations.discord.oauth import DiscordOAuthError, DiscordOAuthGuild
from app.middleware.request_context import RequestContextMiddleware
from app.security.discord_permissions import can_manage_guild
from app.security.session import OperatorSession, SessionService


def test_owner_is_always_eligible() -> None:
    assert can_manage_guild(owner=True, permissions="0") is True


def test_administrator_and_manage_guild_bits() -> None:
    assert can_manage_guild(owner=False, permissions="8") is True
    assert can_manage_guild(owner=False, permissions="32") is True
    assert can_manage_guild(owner=False, permissions="0") is False


def test_large_permission_bitfield_parses() -> None:
    assert can_manage_guild(owner=False, permissions="2147483680") is True


def test_discord_401_maps_to_api_401() -> None:
    with pytest.raises(HTTPException) as raised:
        raise_discord_oauth_http_error(
            DiscordOAuthError("nope", http_status=401, operation="guilds"),
            route="/sessions/servers",
        )
    assert raised.value.status_code == 401
    assert raised.value.detail["code"] == "discord_token_invalid"


def test_discord_429_maps_to_api_429() -> None:
    with pytest.raises(HTTPException) as raised:
        raise_discord_oauth_http_error(
            DiscordOAuthError(
                "slow down",
                http_status=429,
                operation="guilds",
                retry_after="5",
            ),
            route="/sessions/servers",
        )
    assert raised.value.status_code == 429
    assert raised.value.detail["code"] == "discord_rate_limited"
    assert raised.value.headers["Retry-After"] == "5"


def _operator() -> OperatorSession:
    return OperatorSession(
        session_id="sess",
        user_id="42",
        username="operator",
        global_name="Operator",
        avatar=None,
        created_at=0,
        expires_at=2**31 - 1,
    )


def _settings(*, auth_enforced: bool = True) -> Settings:
    return Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment="testing",
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=None,
        database_echo=False,
        auth_enforced=auth_enforced,
        discord_client_id="cid",
        discord_client_secret="secret",
        discord_redirect_uri="https://example.com/callback",
        discord_dashboard_redirect_uri="https://example.com/dashboard/callback",
    )


def _build_app(
    *,
    sessions: SessionService,
    oauth: MagicMock,
    settings: Settings,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(sessions_module.router, prefix="/api/v1")
    app.dependency_overrides[require_operator_session] = lambda: _operator()
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_discord_oauth_client] = lambda: oauth
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def test_list_servers_returns_owned_guild_without_bot_install() -> None:
    sessions = SessionService()
    sessions.get_valid_access_token = AsyncMock(return_value="access-token")  # type: ignore[method-assign]

    oauth = MagicMock()
    oauth.get_current_user_guilds = AsyncMock(
        return_value=[
            DiscordOAuthGuild(
                id="111111111111111111",
                name="Owned Server",
                owner=True,
                permissions="0",
            )
        ]
    )

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.keys = AsyncMock(return_value=[])
    redis.aclose = AsyncMock()

    app = _build_app(sessions=sessions, oauth=oauth, settings=_settings())

    with patch("app.api.v1.sessions.get_redis", AsyncMock(return_value=redis)):
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/sessions/servers",
                headers={"X-Request-ID": "servers-owned-001"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["servers"][0]["id"] == "111111111111111111"
    assert body["servers"][0]["owner"] is True
    assert body["servers"][0]["bot_installed"] is False
    assert isinstance(body["servers"][0]["id"], str)


def test_list_servers_discord_401_returns_structured_error() -> None:
    sessions = SessionService()
    sessions.get_valid_access_token = AsyncMock(  # type: ignore[method-assign]
        side_effect=["stale-access-token", None]
    )
    sessions.clear_oauth_tokens = AsyncMock()  # type: ignore[method-assign]

    oauth = MagicMock()
    oauth.get_current_user_guilds = AsyncMock(
        side_effect=DiscordOAuthError(
            "unauthorized",
            http_status=401,
            operation="current_user_guilds",
        )
    )

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.keys = AsyncMock(return_value=[])
    redis.aclose = AsyncMock()

    app = _build_app(sessions=sessions, oauth=oauth, settings=_settings())

    with patch("app.api.v1.sessions.get_redis", AsyncMock(return_value=redis)):
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/sessions/servers",
                headers={"X-Request-ID": "servers-401-001"},
            )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "discord_token_invalid"
    assert body["error"]["request_id"] == "servers-401-001"
    assert "stale-access-token" not in response.text
