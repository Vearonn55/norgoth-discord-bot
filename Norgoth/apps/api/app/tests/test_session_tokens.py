"""Tests for operator OAuth token sealing in Redis."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.security.session import SessionService, _seal_token, _unseal_token


def _settings(
    *,
    environment: str = "production",
    oauth_token_encryption_key: bytes | None = None,
    webhook_encryption_key: bytes | None = None,
    ip_encryption_key: bytes | None = None,
) -> Settings:
    return Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment=environment,
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=None,
        database_echo=False,
        auth_enforced=environment == "production",
        oauth_token_encryption_key=oauth_token_encryption_key,
        webhook_encryption_key=webhook_encryption_key,
        ip_encryption_key=ip_encryption_key,
    )


def test_seal_token_production_without_key_stores_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.security.session.get_settings",
        lambda: _settings(environment="production"),
    )

    sealed = _seal_token("discord-access-token")

    assert sealed == "discord-access-token"
    assert _unseal_token(sealed) == "discord-access-token"


def test_seal_token_falls_back_to_ip_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = b"i" * 32
    monkeypatch.setattr(
        "app.security.session.get_settings",
        lambda: _settings(environment="production", ip_encryption_key=key),
    )

    sealed = _seal_token("discord-access-token")

    assert sealed.startswith("enc:")
    assert sealed != "discord-access-token"
    assert _unseal_token(sealed) == "discord-access-token"


@pytest.mark.asyncio
async def test_create_session_production_without_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.security.session.get_settings",
        lambda: _settings(environment="production"),
    )

    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.security.session.get_redis",
        AsyncMock(return_value=redis),
    )

    session, exchange_code = await SessionService().create_session(
        user_id="42",
        username="kaan",
        global_name="Kaan",
        avatar=None,
        access_token="access-token",
        refresh_token="refresh-token",
        token_expires_in=3600,
    )

    assert session.user_id == "42"
    assert exchange_code
    stored_values = [call.args[1] for call in redis.set.await_args_list]
    assert "access-token" in stored_values
    assert "refresh-token" in stored_values
