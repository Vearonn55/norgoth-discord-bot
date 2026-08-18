"""Verification callback redirects to the dashboard without OAuth secrets."""

from __future__ import annotations

from types import SimpleNamespace

from starlette.requests import Request

from app.api.v1.oauth import _reason_from_oauth_error, _verify_result_redirect
from app.integrations.discord.oauth import DiscordOAuthError


def _request() -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/v1/oauth/discord/callback",
        "raw_path": b"/api/v1/oauth/discord/callback",
        "query_string": b"code=SECRET&state=SECRET",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "https",
    }
    request = Request(scope)
    request.state.request_id = "cid-123"
    return request


def test_verify_result_redirect_omits_code_and_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.oauth.get_settings",
        lambda: SimpleNamespace(dashboard_public_url="https://www.norbot.io"),
    )
    response = _verify_result_redirect(
        _request(),
        lang="tr",
        outcome="pending",
        reason="high_risk_guild",
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("https://www.norbot.io/tr/verify/result?")
    assert "outcome=pending" in location
    assert "reason=high_risk_guild" in location
    assert "cid=cid-123" in location
    assert "code=" not in location
    assert "state=" not in location
    assert "SECRET" not in location


def test_verify_result_redirect_can_include_display_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.oauth.get_settings",
        lambda: SimpleNamespace(dashboard_public_url="https://www.norbot.io"),
    )
    response = _verify_result_redirect(
        _request(),
        lang="en",
        outcome="granted",
        reason="allowed",
        display_context="signed-context-token",
    )
    location = response.headers["location"]
    assert "ctx=signed-context-token" in location
    assert "code=" not in location
    assert "state=" not in location


def test_oauth_error_reason_split() -> None:
    assert (
        _reason_from_oauth_error(
            DiscordOAuthError("limited", http_status=429, operation="token_exchange")
        )
        == "discord_rate_limited"
    )
    assert (
        _reason_from_oauth_error(
            DiscordOAuthError("expired", http_status=400, operation="token_exchange")
        )
        == "oauth_expired"
    )
    assert (
        _reason_from_oauth_error(
            DiscordOAuthError("guilds", http_status=500, operation="current_user_guilds")
        )
        == "discord_unavailable"
    )
