"""Idempotency / rapid-toggle tests for the write-through config store.

Every config domain follows the same contract: Redis is a cache in front of the
Postgres source of truth. These tests exercise that contract deterministically
with a fake in-memory Redis and a stubbed Postgres loader (no live DB), covering
each feature key registered in :data:`FEATURE_REGISTRY`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services import feature_config_store as store
from app.services.feature_config_store import FEATURE_REGISTRY, guild_key

GUILD_ID = "123456789012345678"


class FakeRedis:
    """Minimal async Redis stand-in supporting ``get``/``set``."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.store.get(key)

    async def set(self, key: str, value: str) -> None:
        self.set_calls += 1
        self.store[key] = value


@pytest.mark.anyio
@pytest.mark.parametrize("feature_key", sorted(FEATURE_REGISTRY.keys()))
async def test_read_through_hydrates_once_then_serves_from_cache(
    feature_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a Redis miss, hydrate from Postgres once; subsequent reads hit cache."""

    payload: dict[str, Any] = {"enabled": True, "feature": feature_key}
    load_calls = 0

    async def _fake_load(guild_id: str, key: str) -> Any:
        nonlocal load_calls
        load_calls += 1
        assert guild_id == GUILD_ID
        assert key == feature_key
        return payload

    monkeypatch.setattr(store, "load_config", _fake_load)

    redis = FakeRedis()

    first = await store.read_through(GUILD_ID, feature_key, redis)
    assert first == payload
    assert load_calls == 1

    # The snapshot is now cached under the canonical key.
    suffix = FEATURE_REGISTRY[feature_key][1]
    assert guild_key(GUILD_ID, suffix) in redis.store

    second = await store.read_through(GUILD_ID, feature_key, redis)
    assert second == payload
    # Postgres is not consulted again: the read is idempotent and cache-served.
    assert load_calls == 1


@pytest.mark.anyio
@pytest.mark.parametrize("feature_key", sorted(FEATURE_REGISTRY.keys()))
async def test_read_raw_returns_cached_json_without_db(
    feature_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warm cache is returned verbatim and never triggers a Postgres load."""

    suffix = FEATURE_REGISTRY[feature_key][1]
    cached = json.dumps({"enabled": False, "cached": True})

    async def _fail_load(guild_id: str, key: str) -> Any:  # pragma: no cover
        raise AssertionError("load_config must not be called on a cache hit")

    monkeypatch.setattr(store, "load_config", _fail_load)

    redis = FakeRedis()
    redis.store[guild_key(GUILD_ID, suffix)] = cached

    raw = await store.read_raw(GUILD_ID, feature_key, redis)
    assert raw == cached


@pytest.mark.anyio
async def test_read_through_returns_none_when_absent_everywhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truly-unset config yields ``None`` from both Redis and Postgres."""

    async def _fake_load(guild_id: str, key: str) -> Any:
        return None

    monkeypatch.setattr(store, "load_config", _fake_load)

    redis = FakeRedis()
    result = await store.read_through(GUILD_ID, "automod", redis)
    assert result is None
