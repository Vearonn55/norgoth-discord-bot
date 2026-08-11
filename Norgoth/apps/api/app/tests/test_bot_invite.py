"""Tests for Discord Guild Install invite URL + /bot-invite authz."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import dashboard_oauth, dependencies_auth
from app.api.v1.dashboard_oauth import router as dashboard_oauth_router
from app.api.v1.dependencies import get_http_client, get_settings
from app.security.discord_permissions import (
    BOT_INSTALL_SCOPES,
    BOT_INVITE_PERMISSIONS_MINIMAL,
    build_bot_invite_url,
)
from app.security.session import COOKIE_NAME, OperatorSession

GUILD_A = "111111111111111111"
GUILD_B = "222222222222222222"
APP_ID = "999888777666555444"


def test_build_bot_invite_url_without_guild() -> None:
    url = build_bot_invite_url(client_id=APP_ID)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert (
        f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        == "https://discord.com/api/oauth2/authorize"
    )
    assert query["client_id"] == [APP_ID]
    assert query["permissions"] == [str(BOT_INVITE_PERMISSIONS_MINIMAL)]
    assert query["scope"] == [BOT_INSTALL_SCOPES]
    assert "response_type" not in query
    assert "guild_id" not in query
    assert "disable_guild_select" not in query
    assert "client_secret" not in query
    assert "redirect_uri" not in query


def test_build_bot_invite_url_with_guild_preselect() -> None:
    url = build_bot_invite_url(client_id=APP_ID, guild_id=GUILD_A)
    query = parse_qs(urlparse(url).query)

    assert query["guild_id"] == [GUILD_A]
    assert query["disable_guild_select"] == ["true"]
    assert query["scope"] == [BOT_INSTALL_SCOPES]
    assert "response_type" not in query


def _operator(user_id: str = "42") -> OperatorSession:
    return OperatorSession(
        session_id="sess",
        user_id=user_id,
        username="operator",
        global_name="Operator",
        avatar=None,
        created_at=0,
        expires_at=2**31 - 1,
    )


def _invite_settings(*, auth_enforced: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        auth_enforced=auth_enforced,
        discord_application_id=APP_ID,
        discord_client_id="client-id",
        discord_client_secret="client-secret",
        discord_redirect_uri="https://example.test/callback",
    )


class _FakeSessions:
    def __init__(self, token: str | None) -> None:
        self._token = token

    async def get_access_token(self, user_id: str) -> str | None:
        return self._token

    async def get_session(self, session_id: str) -> OperatorSession | None:
        if session_id == "sess":
            return _operator()
        return None


class _FakeOAuthClient:
    guilds: list[SimpleNamespace] = []

    def __init__(self, **_: object) -> None:
        pass

    async def get_current_user_guilds(self, *, access_token: str):
        return list(type(self).guilds)


def _build_app(monkeypatch, *, guilds: list[SimpleNamespace], token: str | None = "tok"):
    _FakeOAuthClient.guilds = guilds
    monkeypatch.setattr(dashboard_oauth, "DiscordOAuthClient", _FakeOAuthClient)
    monkeypatch.setattr(
        dashboard_oauth,
        "get_session_service",
        lambda: _FakeSessions(token),
    )
    monkeypatch.setattr(
        dependencies_auth,
        "get_session_service",
        lambda: _FakeSessions(token),
    )

    application = FastAPI()
    application.include_router(dashboard_oauth_router, prefix="/api/v1")
    application.dependency_overrides[get_settings] = lambda: _invite_settings(
        auth_enforced=True
    )

    async def _fake_http():
        yield AsyncMock()

    application.dependency_overrides[get_http_client] = _fake_http
    return application


def test_bot_invite_generic_redirects_without_auth(monkeypatch) -> None:
    application = _build_app(monkeypatch, guilds=[])
    client = TestClient(application)
    response = client.get("/api/v1/oauth/discord/bot-invite", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == [APP_ID]
    assert query["scope"] == [BOT_INSTALL_SCOPES]
    assert "guild_id" not in query
    assert "response_type" not in query


def test_bot_invite_guild_requires_auth_when_enforced(monkeypatch) -> None:
    application = _build_app(monkeypatch, guilds=[])
    client = TestClient(application)
    response = client.get(
        f"/api/v1/oauth/discord/bot-invite?guild_id={GUILD_A}",
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_bot_invite_forbidden_for_non_manager(monkeypatch) -> None:
    application = _build_app(
        monkeypatch,
        guilds=[SimpleNamespace(id=GUILD_A, owner=False, permissions="0")],
    )
    client = TestClient(application)
    response = client.get(
        f"/api/v1/oauth/discord/bot-invite?guild_id={GUILD_A}",
        cookies={COOKIE_NAME: "sess"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_bot_invite_forbidden_for_other_guild(monkeypatch) -> None:
    application = _build_app(
        monkeypatch,
        guilds=[SimpleNamespace(id=GUILD_A, owner=True, permissions="0")],
    )
    client = TestClient(application)
    response = client.get(
        f"/api/v1/oauth/discord/bot-invite?guild_id={GUILD_B}",
        cookies={COOKIE_NAME: "sess"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_bot_invite_authorized_guild_redirects_with_preselect(monkeypatch) -> None:
    application = _build_app(
        monkeypatch,
        guilds=[SimpleNamespace(id=GUILD_A, owner=True, permissions="0")],
    )
    client = TestClient(application)
    response = client.get(
        f"/api/v1/oauth/discord/bot-invite?guild_id={GUILD_A}",
        cookies={COOKIE_NAME: "sess"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["guild_id"] == [GUILD_A]
    assert query["disable_guild_select"] == ["true"]
    assert query["permissions"] == [str(BOT_INVITE_PERMISSIONS_MINIMAL)]
    assert query["scope"] == [BOT_INSTALL_SCOPES]
    assert "response_type" not in query


def test_bot_invite_missing_token_is_unauthorized(monkeypatch) -> None:
    application = _build_app(monkeypatch, guilds=[], token=None)
    client = TestClient(application)
    response = client.get(
        f"/api/v1/oauth/discord/bot-invite?guild_id={GUILD_A}",
        cookies={COOKIE_NAME: "sess"},
        follow_redirects=False,
    )
    assert response.status_code == 401
