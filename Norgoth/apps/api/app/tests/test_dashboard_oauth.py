"""Tests for operator dashboard Discord OAuth authorize and callback."""

from __future__ import annotations

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.dashboard_oauth import router as dashboard_oauth_router
from app.api.v1.dependencies import (
    get_discord_oauth_client,
    get_discord_oauth_state_service,
    get_settings,
)
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.integrations.discord.oauth import DiscordOAuthToken, DiscordOAuthUser
from app.middleware.request_context import RequestContextMiddleware
from app.security.oauth_state import DiscordOAuthStateService
from app.security.session import OperatorSession

CLIENT_SECRET = "discord-client-secret"
DASHBOARD_REDIRECT = "https://api.example.test/api/v1/oauth/discord/dashboard/callback"
DASHBOARD_PUBLIC = "https://www.example.test"


def _settings() -> Settings:
    return Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment="production",
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=None,
        database_echo=False,
        auth_enforced=True,
        discord_client_id="cid",
        discord_client_secret=CLIENT_SECRET,
        discord_redirect_uri="https://api.example.test/api/v1/oauth/discord/callback",
        discord_dashboard_redirect_uri=DASHBOARD_REDIRECT,
        dashboard_public_url=DASHBOARD_PUBLIC,
    )


class _FakeOAuthClient:
    def __init__(self) -> None:
        self.exchange_redirect_uri: str | None = None

    async def exchange_code(self, *, code: str, redirect_uri: str | None = None):
        self.exchange_redirect_uri = redirect_uri
        return DiscordOAuthToken(
            access_token="access-token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh-token",
            scope=frozenset({"identify", "guilds"}),
        )

    async def get_current_user(self, *, access_token: str) -> DiscordOAuthUser:
        return DiscordOAuthUser(
            id="42",
            username="kaan",
            global_name="Kaan",
            avatar=None,
        )


class _FakeSessions:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.created: dict[str, object] | None = None

    async def create_session(self, **kwargs: object) -> tuple[OperatorSession, str]:
        if self.fail:
            raise RuntimeError("OAuth token encryption is required in production.")
        self.created = kwargs
        session = OperatorSession(
            session_id="sess",
            user_id="42",
            username="kaan",
            global_name="Kaan",
            avatar=None,
            created_at=0,
            expires_at=2**31 - 1,
        )
        return session, "one-time-exchange"


def _build_app(*, sessions: _FakeSessions, oauth: _FakeOAuthClient) -> FastAPI:
    settings = _settings()
    state_service = DiscordOAuthStateService(secret=CLIENT_SECRET)

    application = FastAPI()
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(dashboard_oauth_router, prefix="/api/v1")
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_discord_oauth_client] = lambda: oauth
    application.dependency_overrides[get_discord_oauth_state_service] = (
        lambda: state_service
    )
    return application, settings, state_service, sessions


def test_dashboard_callback_redirects_to_auth_complete(monkeypatch) -> None:
    oauth = _FakeOAuthClient()
    sessions = _FakeSessions()
    application, _settings_obj, state_service, _ = _build_app(
        sessions=sessions, oauth=oauth
    )
    monkeypatch.setattr(
        "app.api.v1.dashboard_oauth.get_session_service",
        lambda: sessions,
    )
    monkeypatch.setattr(
        "app.api.v1.dashboard_oauth.consume_oauth_nonce",
        AsyncMock(return_value=None),
    )

    state = state_service.create(
        discord_guild_id="0",
        purpose="dashboard",
        lang="en",
    )

    client = TestClient(application)
    response = client.get(
        "/api/v1/oauth/discord/dashboard/callback",
        params={"code": "discord-code", "state": state},
        follow_redirects=False,
        headers={"X-Request-ID": "oauth-callback-001"},
    )

    assert response.status_code == 303
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert location.startswith(f"{DASHBOARD_PUBLIC}/en/auth/complete")
    assert query["code"] == ["one-time-exchange"]
    assert oauth.exchange_redirect_uri == DASHBOARD_REDIRECT
    assert sessions.created is not None
    assert sessions.created["user_id"] == "42"
    assert sessions.created["access_token"] == "access-token"


def test_dashboard_callback_session_failure_redirects_not_json_500(
    monkeypatch,
) -> None:
    oauth = _FakeOAuthClient()
    sessions = _FakeSessions(fail=True)
    application, _, state_service, _ = _build_app(sessions=sessions, oauth=oauth)
    monkeypatch.setattr(
        "app.api.v1.dashboard_oauth.get_session_service",
        lambda: sessions,
    )
    monkeypatch.setattr(
        "app.api.v1.dashboard_oauth.consume_oauth_nonce",
        AsyncMock(return_value=None),
    )

    state = state_service.create(
        discord_guild_id="0",
        purpose="dashboard",
        lang="tr",
    )

    client = TestClient(application)
    response = client.get(
        "/api/v1/oauth/discord/dashboard/callback",
        params={"code": "discord-code", "state": state},
        follow_redirects=False,
        headers={"X-Request-ID": "oauth-callback-002"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"{DASHBOARD_PUBLIC}/tr?oauth_error=callback"
    assert "internal_server_error" not in response.text


def test_dashboard_callback_invalid_state_redirects(monkeypatch) -> None:
    application, _, _, _ = _build_app(
        sessions=_FakeSessions(), oauth=_FakeOAuthClient()
    )
    monkeypatch.setattr(
        "app.api.v1.dashboard_oauth.consume_oauth_nonce",
        AsyncMock(return_value=None),
    )

    client = TestClient(application)
    response = client.get(
        "/api/v1/oauth/discord/dashboard/callback",
        params={"code": "discord-code", "state": "not-a-valid-state"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "oauth_error=callback" in response.headers["location"]
