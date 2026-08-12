"""Tests for operator Discord guild fetch caching / singleflight."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.operator_discord import (
    _deserialize_guilds,
    _serialize_guilds,
    fetch_operator_guilds,
    invalidate_operator_guilds_cache,
    operator_guilds_cache_key,
)
from app.integrations.discord.oauth import DiscordOAuthGuild


def test_serialize_roundtrip() -> None:
    guilds = [
        DiscordOAuthGuild(
            id="1",
            name="Alpha",
            owner=True,
            permissions="8",
            icon="abc",
        ),
        DiscordOAuthGuild(
            id="2",
            name="Beta",
            owner=False,
            permissions="32",
            icon=None,
        ),
    ]
    restored = _deserialize_guilds(_serialize_guilds(guilds))
    assert restored == guilds


@pytest.mark.asyncio
async def test_fetch_operator_guilds_uses_cache_and_singleflight() -> None:
    guilds = [
        DiscordOAuthGuild(
            id="99",
            name="Cached",
            owner=True,
            permissions="8",
            icon=None,
        )
    ]
    oauth = AsyncMock()
    oauth.get_current_user_guilds = AsyncMock(return_value=guilds)
    sessions = AsyncMock()
    sessions.get_valid_access_token = AsyncMock(return_value="token")

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()

    with patch("app.api.v1.operator_discord.get_redis", AsyncMock(return_value=redis)):
        first, second = await asyncio.gather(
            fetch_operator_guilds(
                sessions=sessions,
                oauth_client=oauth,
                user_id="42",
                route="test-a",
            ),
            fetch_operator_guilds(
                sessions=sessions,
                oauth_client=oauth,
                user_id="42",
                route="test-b",
            ),
        )

    assert first == guilds
    assert second == guilds
    assert oauth.get_current_user_guilds.await_count == 1
    redis.set.assert_any_call(
        operator_guilds_cache_key("42"),
        _serialize_guilds(guilds),
        ex=45,
    )


@pytest.mark.asyncio
async def test_invalidate_operator_guilds_cache() -> None:
    redis = AsyncMock()
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()
    with patch("app.api.v1.operator_discord.get_redis", AsyncMock(return_value=redis)):
        await invalidate_operator_guilds_cache("42")
    assert redis.delete.await_count >= 1
