"""Security regression tests for Phase 0–2 hardening."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.v1.dependencies_auth import require_platform_admin
from app.core.config import Settings
from app.middleware.csrf_origin import CsrfOriginMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.campaigns import _filter_campaigns_for_operator
from app.routes.content_notifications import _assert_guild_owned_template
from app.security.client_ip import get_trusted_client_ip
from app.security.internal_auth import require_internal_token
from app.security.session import COOKIE_NAME, OperatorSession


GUILD_A = "111111111111111111"
GUILD_B = "222222222222222222"


def _operator(user_id: str = "42") -> OperatorSession:
    return OperatorSession(
        session_id="sess-secret",
        user_id=user_id,
        username="operator",
        global_name="Operator",
        avatar=None,
        created_at=0,
        expires_at=2**31 - 1,
    )


def test_public_session_omits_session_id() -> None:
    payload = _operator().to_public_dict()
    assert "session_id" not in payload
    assert payload["user_id"] == "42"


def test_sessions_me_body_omits_session_id() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/me")

    assert response.status_code == 200
    body = response.json()
    if body.get("user"):
        assert "session_id" not in body["user"]


def test_guild_put_requires_internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.security.internal_auth.get_settings",
        lambda: SimpleNamespace(
            internal_token="internal-secret",
            discord_bot_token="bot-secret",
        ),
    )
    application = FastAPI()

    @application.put(
        "/guilds/{discord_guild_id}",
        dependencies=[Depends(require_internal_token)],
    )
    def _put(discord_guild_id: str) -> dict[str, str]:
        return {"id": discord_guild_id}

    client = TestClient(application)
    assert client.put("/guilds/123456789012345678").status_code == 401
    allowed = client.put(
        "/guilds/123456789012345678",
        headers={"X-Norgoth-Internal-Token": "internal-secret"},
    )
    assert allowed.status_code == 200
    bot_fallback = client.put(
        "/guilds/123456789012345678",
        headers={"X-Norgoth-Bot-Token": "bot-secret"},
    )
    assert bot_fallback.status_code == 200


def test_campaign_list_filters_to_manageable_guilds() -> None:
    campaigns = [
        {"id": "a", "guild_id": GUILD_A},
        {"id": "b", "guild_id": GUILD_B},
    ]
    filtered = _filter_campaigns_for_operator(campaigns, {GUILD_A})
    assert [row["id"] for row in filtered] == ["a"]


def test_platform_admin_queue_control_denied_by_default() -> None:
    settings = SimpleNamespace(auth_enforced=True, platform_admin_ids=())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_platform_admin(_operator(), settings))
    assert exc.value.status_code == 403


def test_platform_admin_allowlist_permits_operator() -> None:
    settings = SimpleNamespace(auth_enforced=True, platform_admin_ids=("42",))
    result = asyncio.run(require_platform_admin(_operator(), settings))
    assert result.user_id == "42"


@pytest.mark.asyncio
async def test_cross_guild_template_id_rejected() -> None:
    class _EmptySession:
        async def scalar(self, _stmt):  # noqa: ANN001
            return None

    with pytest.raises(HTTPException) as exc:
        await _assert_guild_owned_template(
            _EmptySession(),  # type: ignore[arg-type]
            guild_id=GUILD_A,
            template_id=uuid4(),
        )
    assert exc.value.status_code == 400


def test_csrf_rejects_cross_origin_cookie_post() -> None:
    settings = Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment="testing",
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=None,
        database_echo=False,
        dashboard_public_url="https://www.norbot.io",
    )
    application = FastAPI()
    application.add_middleware(CsrfOriginMiddleware, settings=settings)

    @application.post("/campaigns")
    def _create() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(application)
    client.cookies.set(COOKIE_NAME, "sess")
    denied = client.post("/campaigns")
    assert denied.status_code == 403
    cross = client.post(
        "/campaigns",
        headers={"Origin": "https://evil.example"},
    )
    assert cross.status_code == 403
    allowed = client.post(
        "/campaigns",
        headers={"Origin": "https://www.norbot.io"},
    )
    assert allowed.status_code == 200


def test_spoofed_forwarded_for_ignored_from_untrusted_peer() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (b"x-forwarded-for", b"203.0.113.10"),
            (b"x-real-ip", b"198.51.100.20"),
        ],
        "client": ("203.0.113.99", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    assert get_trusted_client_ip(Request(scope)) == "203.0.113.99"


def test_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRedis:
        def __init__(self) -> None:
            self.count = 0

        async def incr(self, _key: str) -> int:
            self.count += 1
            return self.count

        async def expire(self, _key: str, _seconds: int) -> bool:
            return True

        async def aclose(self) -> None:
            return None

    fake = _FakeRedis()
    fake.count = 240

    async def _get_redis():
        return fake

    monkeypatch.setattr(
        "app.middleware.rate_limit.get_settings",
        lambda: SimpleNamespace(environment="development"),
    )
    monkeypatch.setattr("app.middleware.rate_limit.get_redis", _get_redis)

    application = FastAPI()
    application.add_middleware(RateLimitMiddleware)

    @application.get("/api/v1/guilds/1/modules")
    def _probe() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(application) as client:
        response = client.get("/api/v1/guilds/1/modules")
    assert response.status_code == 429
