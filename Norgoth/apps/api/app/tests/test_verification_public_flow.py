"""Tests for Member Verification setup state, HTML, and OAuth helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.api.v1.oauth import (
    ProxycheckSignals,
    _get_client_ip,
    _proxycheck_vpn_or_proxy_detected,
    authorize_discord,
)
from app.integrations.discord.cdn import discord_icon_url
from app.integrations.proxycheck import ProxycheckError
from app.models.enums import RiskAction
from app.services.verification_html import (
    render_verification_result_page,
    render_verification_unavailable_page,
)
from app.services.verification_setup import derive_verification_setup_state
from app.services.views import ConfigurationView


def _config(**overrides: object) -> ConfigurationView:
    base: dict[str, object] = dict(
        id=uuid4(),
        guild_id=uuid4(),
        verification_channel_id="111",
        log_channel_id="222",
        unverified_role_id="333",
        member_role_id="444",
        manual_review_role_id="",
        minimum_account_age_days=7,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        vpn_or_proxy_action=RiskAction.DENY,
        shared_ip_action=RiskAction.DENY,
        enabled=True,
        panel_message_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return ConfigurationView(**base)  # type: ignore[arg-type]


def test_setup_state_matrix() -> None:
    assert derive_verification_setup_state(None).state == "not_configured"
    incomplete = _config(verification_channel_id="", enabled=True)
    assert derive_verification_setup_state(incomplete).state == "incomplete"
    # Log channel is owned by Discord Logs; missing legacy log is not incomplete.
    without_log = _config(log_channel_id="", enabled=True)
    assert derive_verification_setup_state(without_log).state == "active"
    disabled = _config(enabled=False)
    assert derive_verification_setup_state(disabled).state == "disabled"
    active = _config(enabled=True)
    assert derive_verification_setup_state(active).state == "active"
    degraded = derive_verification_setup_state(active, degraded=True)
    assert degraded.state == "degraded"
    error = derive_verification_setup_state(active, error=True)
    assert error.state == "error"


def test_discord_icon_url_variants() -> None:
    assert discord_icon_url("1", None) is None
    assert discord_icon_url("1", "abc") == (
        "https://cdn.discordapp.com/icons/1/abc.png?size=128"
    )
    assert discord_icon_url("1", "a_abc", size=64) == (
        "https://cdn.discordapp.com/icons/1/a_abc.gif?size=64"
    )


def test_public_html_branding_and_no_secrets() -> None:
    html = render_verification_unavailable_page(
        guild_name="Norgoth 123",
        message="Verification is not configured for this server.",
        icon_url="https://cdn.discordapp.com/icons/1/abc.png?size=128",
        lang="en",
    )
    assert "NorBot Verification" in html
    assert "Norgoth Verification" not in html
    assert "Norgoth 123" in html
    assert "cdn.discordapp.com" in html
    assert "client_secret" not in html.lower()
    assert "access_token" not in html.lower()

    result = render_verification_result_page(
        allowed=True,
        manual_review=False,
        reason="allowed",
        username="Ada",
        guild_name="Norgoth 123",
        icon_url=None,
        lang="tr",
        role_grant_failed=True,
    )
    assert "NorBot Verification" in result
    assert "rol" in result.lower() or "role" in result.lower()
    assert "203.0.113" not in result


def test_get_client_ip_prefers_proxy_headers() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (b"x-forwarded-for", b"203.0.113.10, 10.0.0.1"),
            (b"x-real-ip", b"198.51.100.20"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert _get_client_ip(request) == "198.51.100.20"

    scope2 = dict(scope)
    scope2["headers"] = [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")]
    assert _get_client_ip(Request(scope2)) == "203.0.113.10"


def test_get_client_ip_ignores_spoofed_headers_from_untrusted_peer() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"198.51.100.1")],
        "client": ("8.8.8.8", 443),
        "server": ("test", 80),
        "scheme": "http",
    }
    assert _get_client_ip(Request(scope)) == "8.8.8.8"


@pytest.mark.asyncio
async def test_proxycheck_failure_does_not_block_verification_flow() -> None:
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": "/api/v1/oauth/discord/callback",
            "raw_path": b"/api/v1/oauth/discord/callback",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "scheme": "https",
        }
    )
    request.state.request_id = "verify-risk-fallback"
    proxycheck_client = SimpleNamespace(
        check_ip=AsyncMock(side_effect=ProxycheckError("provider unavailable"))
    )

    result = await _proxycheck_vpn_or_proxy_detected(
        request=request,
        configuration=_config(deny_vpn_or_proxy=True),
        proxycheck_client=proxycheck_client,
        client_ip="203.0.113.5",
        guild_id="99",
    )

    assert result == ProxycheckSignals(
        vpn_or_proxy_detected=False,
        risk_provider_unavailable=True,
        proxy_classification=None,
    )
    proxycheck_client.check_ip.assert_awaited_once_with("203.0.113.5")


@pytest.mark.asyncio
async def test_authorize_not_configured_html(monkeypatch: pytest.MonkeyPatch) -> None:
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(
            return_value=SimpleNamespace(
                id=uuid4(),
                discord_guild_name="Norgoth 123",
            )
        )
    )
    configuration_service = SimpleNamespace(get_by_guild_id=AsyncMock(return_value=None))
    oauth_client = SimpleNamespace(build_authorization_url=MagicMock())
    oauth_state_service = SimpleNamespace(
        create=MagicMock(),
        create_display_context=MagicMock(return_value="ctx-token"),
    )

    async def fake_meta(**kwargs):  # noqa: ANN003
        return SimpleNamespace(
            name=kwargs["fallback_name"],
            icon_url="https://cdn.discordapp.com/icons/99/abc.png?size=128",
            guild_id=kwargs["discord_guild_id"],
            icon_hash="abc",
        )

    monkeypatch.setattr(
        "app.api.v1.oauth.resolve_guild_public_meta",
        fake_meta,
    )
    monkeypatch.setattr(
        "app.api.v1.oauth.enforce_verification_rate_limit",
        AsyncMock(),
    )

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/v1/oauth/discord/authorize/99",
        "raw_path": b"/api/v1/oauth/discord/authorize/99",
        "query_string": b"lang=en",
        "headers": [(b"x-real-ip", b"203.0.113.5")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)

    response = await authorize_discord(
        request=request,
        discord_guild_id="99",
        oauth_client=oauth_client,
        oauth_state_service=oauth_state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        bot_client=None,
    )

    assert response.status_code == 303
    assert "verify?state=not_configured" in response.headers["location"]
    assert "ctx=ctx-token" in response.headers["location"]
    oauth_client.build_authorization_url.assert_not_called()


@pytest.mark.asyncio
async def test_authorize_active_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = _config(enabled=True)
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(
            return_value=SimpleNamespace(
                id=configuration.guild_id,
                discord_guild_name="Active Guild",
            )
        )
    )
    configuration_service = SimpleNamespace(
        get_by_guild_id=AsyncMock(return_value=configuration)
    )
    oauth_client = SimpleNamespace(
        build_authorization_url=MagicMock(return_value="https://discord.com/oauth")
    )
    oauth_state_service = SimpleNamespace(
        create=MagicMock(return_value="signed.state"),
        create_display_context=MagicMock(return_value="ctx-token"),
    )

    async def fake_meta(**kwargs):  # noqa: ANN003
        return SimpleNamespace(
            name="Active Guild",
            icon_url=None,
            guild_id=kwargs["discord_guild_id"],
            icon_hash=None,
        )

    monkeypatch.setattr("app.api.v1.oauth.resolve_guild_public_meta", fake_meta)
    monkeypatch.setattr(
        "app.api.v1.oauth.enforce_verification_rate_limit",
        AsyncMock(),
    )

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/x",
        "raw_path": b"/x",
        "query_string": b"",
        "headers": [(b"x-real-ip", b"203.0.113.5")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }

    response = await authorize_discord(
        request=Request(scope),
        discord_guild_id="99",
        oauth_client=oauth_client,
        oauth_state_service=oauth_state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        bot_client=None,
    )
    assert response.status_code == 303
    assert "verify?state=ready" in response.headers["location"]
    assert "ctx=ctx-token" in response.headers["location"]
    oauth_client.build_authorization_url.assert_not_called()

    start_response = await authorize_discord(
        request=Request(scope),
        discord_guild_id="99",
        oauth_client=oauth_client,
        oauth_state_service=oauth_state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        bot_client=None,
        start=True,
    )
    assert start_response.status_code == 307
    assert start_response.headers["location"] == "https://discord.com/oauth"


def test_configuration_router_exposes_setup_and_validate() -> None:
    from app.api.v1.router import api_router

    application = FastAPI()
    application.include_router(api_router)
    paths = application.openapi()["paths"]
    assert "/guilds/{discord_guild_id}/configuration/setup" in paths
    assert "/guilds/{discord_guild_id}/configuration/validate" in paths
