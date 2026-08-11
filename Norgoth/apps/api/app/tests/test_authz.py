"""Authorization tests for guild-manager guarded routes.

These cover the guarded-router hardening from Phase 1: guild-scoped mutations
must verify the authenticated operator manages the requested guild, and the
dev-bypass path (auth not enforced) must keep working locally.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import dependencies_auth
from app.api.v1.dependencies_auth import require_guild_manager
from app.core.config import get_settings
from app.routes.modules import router as modules_router
from app.security.session import OperatorSession

GUILD_A = "111111111111111111"
GUILD_B = "222222222222222222"


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


def _enforced_settings() -> SimpleNamespace:
    return SimpleNamespace(
        auth_enforced=True,
        discord_client_id="client-id",
        discord_client_secret="client-secret",
        discord_redirect_uri="https://example.test/callback",
    )


class _FakeSessions:
    def __init__(self, token: str | None) -> None:
        self._token = token

    async def get_access_token(self, user_id: str) -> str | None:
        return self._token


class _FakeOAuthClient:
    """Stands in for DiscordOAuthClient; returns a fixed guild list."""

    guilds: list[SimpleNamespace] = []

    def __init__(self, **_: object) -> None:
        pass

    async def get_current_user_guilds(self, *, access_token: str):
        return list(type(self).guilds)


def _patch_oauth(monkeypatch, guilds: list[SimpleNamespace]) -> None:
    _FakeOAuthClient.guilds = guilds
    monkeypatch.setattr(dependencies_auth, "DiscordOAuthClient", _FakeOAuthClient)


def test_dev_bypass_allows_stub_operator() -> None:
    """When auth is not enforced, the dev stub operator (user 0) is allowed."""

    session = OperatorSession(
        session_id="dev",
        user_id="0",
        username="dev",
        global_name="Developer",
        avatar=None,
        created_at=0,
        expires_at=2**31 - 1,
    )
    settings = SimpleNamespace(auth_enforced=False)

    result = asyncio.run(
        require_guild_manager(
            GUILD_A,
            session,
            http_client=None,
            sessions=_FakeSessions(None),
            settings=settings,
        )
    )

    assert result is session


def test_manager_of_guild_is_authorized(monkeypatch) -> None:
    """A user who owns/administers the guild passes the guard."""

    _patch_oauth(
        monkeypatch,
        [SimpleNamespace(id=GUILD_A, owner=True, permissions="0")],
    )

    result = asyncio.run(
        require_guild_manager(
            GUILD_A,
            _operator(),
            http_client=None,
            sessions=_FakeSessions("token"),
            settings=_enforced_settings(),
        )
    )

    assert result.user_id == "42"


def test_non_manager_is_forbidden(monkeypatch) -> None:
    """A member without manage permission is rejected with 403."""

    _patch_oauth(
        monkeypatch,
        [SimpleNamespace(id=GUILD_A, owner=False, permissions="0")],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            require_guild_manager(
                GUILD_A,
                _operator(),
                http_client=None,
                sessions=_FakeSessions("token"),
                settings=_enforced_settings(),
            )
        )

    assert exc.value.status_code == 403


def test_cross_tenant_access_is_forbidden(monkeypatch) -> None:
    """A manager of Guild A cannot mutate Guild B."""

    _patch_oauth(
        monkeypatch,
        [SimpleNamespace(id=GUILD_A, owner=True, permissions="0")],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            require_guild_manager(
                GUILD_B,
                _operator(),
                http_client=None,
                sessions=_FakeSessions("token"),
                settings=_enforced_settings(),
            )
        )

    assert exc.value.status_code == 403


def test_missing_session_is_unauthorized_over_http() -> None:
    """With auth enforced and no session cookie, a guarded route returns 401."""

    application = FastAPI()
    application.include_router(modules_router)
    application.dependency_overrides[get_settings] = _enforced_settings

    client = TestClient(application)
    response = client.get(f"/guilds/{GUILD_A}/modules")

    assert response.status_code == 401
