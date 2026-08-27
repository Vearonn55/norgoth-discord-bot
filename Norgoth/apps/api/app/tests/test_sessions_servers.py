"""Tests for Discord permission helpers and session server listing."""

from __future__ import annotations

import json
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
from app.integrations.discord.cdn import discord_icon_url
from app.security.discord_permissions import can_manage_guild, guild_role_label
from app.services.guild_setup_state import derive_setup_state
from app.security.session import OperatorSession, SessionService


def test_animated_icon_uses_gif_and_static_uses_png() -> None:
    animated = discord_icon_url("111", "a_abc123", size=128)
    static = discord_icon_url("111", "abc123", size=64)
    assert animated == "https://cdn.discordapp.com/icons/111/a_abc123.gif?size=128"
    assert static == "https://cdn.discordapp.com/icons/111/abc123.png?size=64"
    assert discord_icon_url("111", None) is None


def test_guild_role_label_from_owner_and_bits() -> None:
    assert guild_role_label(owner=True, permissions="0") == "Owner"
    assert guild_role_label(owner=False, permissions="8") == "Administrator"
    assert guild_role_label(owner=False, permissions="32") == "Manage Server"


def test_setup_state_matrix() -> None:
    assert derive_setup_state(bot_installed=False) == "not_installed"
    assert derive_setup_state(bot_installed=True) == "installed"


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
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()

    app = _build_app(sessions=sessions, oauth=oauth, settings=_settings())

    with patch("app.api.v1.sessions.get_redis", AsyncMock(return_value=redis)):
        with patch(
            "app.api.v1.operator_discord.get_redis",
            AsyncMock(return_value=redis),
        ):
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
    assert body["servers"][0]["setup_state"] == "not_installed"
    assert body["servers"][0]["role_label"] == "Owner"
    assert body["servers"][0]["manageable"] is True
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
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()

    app = _build_app(sessions=sessions, oauth=oauth, settings=_settings())

    with patch("app.api.v1.sessions.get_redis", AsyncMock(return_value=redis)):
        with patch(
            "app.api.v1.operator_discord.get_redis",
            AsyncMock(return_value=redis),
        ):
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


def test_list_servers_install_state_and_animated_icon() -> None:
    sessions = SessionService()
    sessions.get_valid_access_token = AsyncMock(return_value="access-token")  # type: ignore[method-assign]

    oauth = MagicMock()
    oauth.get_current_user_guilds = AsyncMock(
        return_value=[
            DiscordOAuthGuild(
                id="111",
                name="Owned Uninstalled",
                owner=True,
                permissions="0",
                icon="staticicon",
            ),
            DiscordOAuthGuild(
                id="222",
                name="Installed Alpha",
                owner=False,
                permissions="8",
                icon="a_animicon",
            ),
            DiscordOAuthGuild(
                id="333",
                name="Installed Beta",
                owner=False,
                permissions="32",
            ),
            DiscordOAuthGuild(
                id="444",
                name="Kicked Bot",
                owner=True,
                permissions="0",
            ),
        ]
    )

    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "guilds": [
                    {"id": "222", "name": "Installed Alpha", "icon": "a_animicon"},
                    {"id": "333", "name": "Installed Beta"},
                ]
            }
        )
    )
    redis.keys = AsyncMock(return_value=[])
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()

    app = _build_app(sessions=sessions, oauth=oauth, settings=_settings())

    with patch("app.api.v1.sessions.get_redis", AsyncMock(return_value=redis)):
        with patch(
            "app.api.v1.operator_discord.get_redis",
            AsyncMock(return_value=redis),
        ):
            with TestClient(app) as client:
                response = client.get("/api/v1/sessions/servers")

    assert response.status_code == 200
    body = response.json()["servers"]
    by_id = {item["id"]: item for item in body}
    assert set(by_id) == {"111", "222", "333", "444"}
    assert all(isinstance(guild_id, str) for guild_id in by_id)
    assert by_id["111"]["setup_state"] == "not_installed"
    assert by_id["111"]["bot_installed"] is False
    assert by_id["111"]["icon_url"].endswith("staticicon.png?size=128")
    assert by_id["222"]["setup_state"] == "installed"
    assert by_id["222"]["bot_installed"] is True
    assert by_id["222"]["role_label"] == "Administrator"
    assert by_id["222"]["icon_url"].endswith("a_animicon.gif?size=128")
    assert by_id["333"]["setup_state"] == "installed"
    assert by_id["333"]["bot_installed"] is True
    assert by_id["333"]["role_label"] == "Manage Server"
    assert by_id["444"]["setup_state"] == "not_installed"
    assert by_id["444"]["bot_installed"] is False
    # Installed servers sort before not-installed; name tie-break within groups.
    assert [item["id"] for item in body] == ["222", "333", "444", "111"]
