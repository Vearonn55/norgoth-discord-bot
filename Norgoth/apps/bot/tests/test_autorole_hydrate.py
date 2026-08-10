"""Tests for automation config hydrate on Redis miss and auto-role helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.state import BotState, automation_key  # noqa: E402


class FakeRedis:
    def __init__(self, data: dict[str, str] | None = None) -> None:
        self.data = dict(data or {})
        self.sets: list[tuple[str, str]] = []

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.sets.append((key, value))

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_get_automation_config_returns_redis_hit() -> None:
    payload = {"auto_role_enabled": True, "auto_role_ids": ["111"]}
    fake = FakeRedis({automation_key(99): json.dumps(payload)})

    with patch("bot.state.redis.from_url", return_value=fake):
        state = BotState("redis://localhost", api_base_url="http://api", bot_token="t")
        state._redis = fake  # type: ignore[assignment]

    result = await state.get_automation_config(99)
    assert result == payload
    assert fake.sets == []


@pytest.mark.asyncio
async def test_get_automation_config_hydrates_on_miss() -> None:
    payload = {"auto_role_enabled": True, "auto_role_ids": ["222"]}
    fake = FakeRedis()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "guild_id": "55",
        "feature_key": "automation",
        "config": payload,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("bot.state.redis.from_url", return_value=fake):
        state = BotState(
            "redis://localhost",
            api_base_url="http://api.example",
            bot_token="secret",
        )
        state._redis = fake  # type: ignore[assignment]

    with patch("bot.state.httpx.AsyncClient", return_value=mock_client):
        result = await state.get_automation_config(55)

    assert result == payload
    assert automation_key(55) in fake.data
    assert json.loads(fake.data[automation_key(55)]) == payload
    mock_client.get.assert_awaited_once()
    called_url = mock_client.get.await_args.args[0]
    assert called_url.endswith("/internal/config/55/automation")


@pytest.mark.asyncio
async def test_get_automation_config_miss_without_api_returns_empty() -> None:
    fake = FakeRedis()
    with patch("bot.state.redis.from_url", return_value=fake):
        state = BotState("redis://localhost")
        state._redis = fake  # type: ignore[assignment]

    result = await state.get_automation_config(1)
    assert result == {}


@pytest.mark.asyncio
async def test_apply_auto_role_skips_when_disabled() -> None:
    from bot.client import NorgothBot

    bot = MagicMock(spec=NorgothBot)
    bot.state = MagicMock()
    bot.state.get_automation_config = AsyncMock(
        return_value={"auto_role_enabled": False, "auto_role_ids": ["1"]}
    )
    bot.publish_autorole_status = AsyncMock()

    member = MagicMock()
    member.guild.id = 10
    member.id = 20
    member.name = "alice"

    # Bind unbound method
    await NorgothBot.apply_auto_role(bot, member)
    member.add_roles.assert_not_called()
    bot.publish_autorole_status.assert_not_called()


@pytest.mark.asyncio
async def test_apply_auto_role_grants_on_join_config() -> None:
    import discord
    from bot.client import NorgothBot

    bot = MagicMock(spec=NorgothBot)
    bot.state = MagicMock()
    bot.state.get_automation_config = AsyncMock(
        return_value={
            "auto_role_enabled": True,
            "auto_role_ids": ["999"],
        }
    )
    bot.publish_autorole_status = AsyncMock()

    role = MagicMock()
    role.id = 999
    role.name = "Member"

    member = MagicMock()
    member.guild.id = 10
    member.guild.get_role = MagicMock(return_value=role)
    member.id = 20
    member.name = "alice"
    member.add_roles = AsyncMock()

    await NorgothBot.apply_auto_role(bot, member)
    member.add_roles.assert_awaited_once()
    bot.publish_autorole_status.assert_awaited_once()
    kwargs = bot.publish_autorole_status.await_args.kwargs
    assert kwargs["ok"] is True
    assert "999" in kwargs["role_ids"]


@pytest.mark.asyncio
async def test_apply_auto_role_logs_forbidden() -> None:
    import discord
    from bot.client import NorgothBot

    bot = MagicMock(spec=NorgothBot)
    bot.state = MagicMock()
    bot.state.get_automation_config = AsyncMock(
        return_value={
            "auto_role_enabled": True,
            "auto_role_ids": ["999"],
        }
    )
    bot.publish_autorole_status = AsyncMock()

    role = MagicMock()
    role.id = 999
    role.name = "Admin"

    member = MagicMock()
    member.guild.id = 10
    member.guild.get_role = MagicMock(return_value=role)
    member.id = 20
    member.name = "alice"
    member.add_roles = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "nope"))

    await NorgothBot.apply_auto_role(bot, member)
    kwargs = bot.publish_autorole_status.await_args.kwargs
    assert kwargs["ok"] is False
    assert "Manage Roles" in kwargs["reason"] or "below target" in kwargs["reason"]
