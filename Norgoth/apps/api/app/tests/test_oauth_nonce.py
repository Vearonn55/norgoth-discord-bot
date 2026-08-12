"""Tests for one-time OAuth nonce consumption."""

from __future__ import annotations

import pytest

from app.security.oauth_nonce import OAuthNonceReplayError, consume_oauth_nonce


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_oauth_nonce_consume_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()

    async def get_redis():
        return fake

    monkeypatch.setattr("app.security.oauth_nonce.get_redis", get_redis)

    await consume_oauth_nonce("nonce-1")
    with pytest.raises(OAuthNonceReplayError):
        await consume_oauth_nonce("nonce-1")
