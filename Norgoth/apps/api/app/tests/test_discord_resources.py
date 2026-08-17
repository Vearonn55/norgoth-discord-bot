"""Guild discord-resources serialize, cache, and force-refresh helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.routes.bot import (
    _serialize_live_resources,
    annotate_resources,
    get_guild_discord_resources,
    guild_resources_key,
    guild_resources_refresh_cooldown_key,
    guild_resources_refresh_lock_key,
    raise_discord_resource_error,
)


def test_serialize_includes_text_and_announcement_not_voice() -> None:
    payload = _serialize_live_resources(
        guild_id="1",
        guild_payload={"name": "Guild", "emojis": []},
        channels=[
            {"id": "10", "name": "general", "type": 0, "parent_id": "40"},
            {"id": "11", "name": "news", "type": 5, "parent_id": "40"},
            {"id": "12", "name": "voice", "type": 2},
            {"id": "40", "name": "Chat", "type": 4},
        ],
        roles=[],
    )
    ids = {row["id"] for row in payload["channels"]}
    assert ids == {"10", "11"}
    assert payload["categories"] == [{"id": "40", "name": "Chat"}]
    assert payload["channels"][0]["type"] == "text"


def test_annotate_resources_marks_fresh_vs_cache() -> None:
    body = annotate_resources({"channels": []}, source="fresh", refreshed=True)
    assert body["source"] == "fresh"
    assert body["refreshed"] is True


def test_rate_limit_maps_to_429() -> None:
    with pytest.raises(HTTPException) as err:
        raise_discord_resource_error(DiscordBotAPIError("limited", status_code=429))
    assert err.value.status_code == 429
    assert err.value.detail["code"] == "discord_rate_limited"
    assert err.value.headers is not None
    assert err.value.headers.get("Retry-After") == "5"


def test_forbidden_maps_to_missing_permissions() -> None:
    with pytest.raises(HTTPException) as err:
        raise_discord_resource_error(DiscordBotAPIError("nope", status_code=403))
    assert err.value.status_code == 503
    assert err.value.detail["code"] == "missing_bot_permissions"


def test_not_found_maps_to_bot_not_installed() -> None:
    with pytest.raises(HTTPException) as err:
        raise_discord_resource_error(DiscordBotAPIError("gone", status_code=404))
    assert err.value.status_code == 404
    assert err.value.detail["code"] == "bot_not_installed"


class _FakeRedis:
    def __init__(self, mapping: dict[str, Any] | None = None) -> None:
        self.store: dict[str, Any] = dict(mapping or {})
        self.set_calls: list[tuple[Any, ...]] = []

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        self.set_calls.append((key, value, nx, ex))
        if nx and self.store.get(key) is not None:
            return None
        self.store[key] = value
        return True

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def aclose(self) -> None:
        return None


def _request() -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(request_id="test-request"))


def _cached_blob() -> dict[str, Any]:
    return {"guild_id": "1", "guild_name": "Cached", "channels": [], "roles": []}


@pytest.mark.asyncio
async def test_refresh_false_returns_cache_without_live_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis({guild_resources_key("1"): json.dumps(_cached_blob())})
    bot = AsyncMock()
    monkeypatch.setattr("app.routes.bot.get_redis", AsyncMock(return_value=redis))

    result = await get_guild_discord_resources(_request(), "1", bot, refresh=False)

    assert result["source"] == "cache"
    assert result["refreshed"] is False
    bot.get_guild.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_true_returns_cache_during_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis(
        {
            guild_resources_key("1"): json.dumps(_cached_blob()),
            guild_resources_refresh_cooldown_key("1"): "1",
        }
    )
    bot = AsyncMock()
    monkeypatch.setattr("app.routes.bot.get_redis", AsyncMock(return_value=redis))

    result = await get_guild_discord_resources(_request(), "1", bot, refresh=True)

    assert result["source"] == "cache"
    assert result["refreshed"] is False
    bot.get_guild.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_true_live_fills_and_marks_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis()
    bot = AsyncMock()
    bot.get_guild = AsyncMock(return_value={"name": "Live Guild", "emojis": []})
    bot.list_guild_channels = AsyncMock(
        return_value=[
            {"id": "10", "name": "general", "type": 0},
            {"id": "11", "name": "news", "type": 5},
        ]
    )
    bot.list_guild_roles = AsyncMock(return_value=[])
    monkeypatch.setattr("app.routes.bot.get_redis", AsyncMock(return_value=redis))

    result = await get_guild_discord_resources(_request(), "1", bot, refresh=True)

    assert result["source"] == "fresh"
    assert result["refreshed"] is True
    assert {row["id"] for row in result["channels"]} == {"10", "11"}
    bot.get_guild.assert_awaited_once()
    assert guild_resources_refresh_cooldown_key("1") in redis.store
    assert guild_resources_refresh_lock_key("1") not in redis.store


@pytest.mark.asyncio
async def test_refresh_true_waits_for_lock_then_returns_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = _FakeRedis(
        {
            guild_resources_key("1"): json.dumps(_cached_blob()),
            guild_resources_refresh_lock_key("1"): "1",
        }
    )
    bot = AsyncMock()
    monkeypatch.setattr("app.routes.bot.get_redis", AsyncMock(return_value=redis))

    async def instant_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.routes.bot.asyncio.sleep", instant_sleep)

    result = await get_guild_discord_resources(_request(), "1", bot, refresh=True)

    assert result["source"] == "cache"
    assert result["refreshed"] is False
    bot.get_guild.assert_not_awaited()

