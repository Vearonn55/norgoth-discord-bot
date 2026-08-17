"""AutoModCog evaluation, claims, and permission-safe actions."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import discord  # noqa: E402

from bot.automod import AutoModCog, DEFAULT_CONFIG  # noqa: E402


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def incr(self, key: str) -> int:
        count = int(self.store.get(key, "0")) + 1
        self.store[key] = str(count)
        return count

    async def expire(self, key: str, _ttl: int) -> None:
        return None

    async def hgetall(self, _key: str) -> dict[str, str]:
        return {}

    async def hset(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def delete(self, *_args: object) -> None:
        return None


def _cog() -> AutoModCog:
    bot = SimpleNamespace(
        user=SimpleNamespace(id=1),
        state=SimpleNamespace(
            redis=FakeRedis(),
            get_json=AsyncMock(return_value={}),
            set_json=AsyncMock(),
            _hydrate_feature_from_api=AsyncMock(return_value={}),
            is_module_enabled=AsyncMock(return_value=True),
            append_moderation_log=AsyncMock(),
            get_automation_config=AsyncMock(return_value={}),
        ),
        get_cog=MagicMock(return_value=None),
    )
    return AutoModCog(bot)  # type: ignore[arg-type]


def _image(content_type: str = "image/png") -> SimpleNamespace:
    return SimpleNamespace(content_type=content_type, filename="a.png")


def _message(
    *,
    content: str = "",
    attachments: list[object] | None = None,
    channel_id: int = 111,
    parent_id: int | None = None,
    guild_id: int = 99,
) -> SimpleNamespace:
    channel = SimpleNamespace(id=channel_id, parent_id=parent_id, name="general", mention="#general")
    guild = SimpleNamespace(id=guild_id)
    author = SimpleNamespace(id=7, mention="<@7>", bot=False)
    return SimpleNamespace(
        id=42,
        content=content,
        attachments=attachments or [],
        stickers=[],
        poll=None,
        embeds=[],
        message_snapshots=None,
        flags=SimpleNamespace(is_forwarded=False),
        type=SimpleNamespace(name="default"),
        channel=channel,
        guild=guild,
        author=author,
        mentions=[],
        role_mentions=[],
        mention_everyone=False,
        edited_at=None,
        delete=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_evaluate_image_only_rejects_text() -> None:
    cog = _cog()
    config = {
        **DEFAULT_CONFIG,
        "image_only_enabled": True,
        "image_only_channel_ids": ["111"],
        "image_only_action": "delete",
        "words_enabled": False,
        "spam_enabled": False,
        "duplicate_enabled": False,
        "mass_mention_enabled": False,
        "block_invites": False,
    }
    result = await cog.evaluate_message(_message(content="hello"), config)  # type: ignore[arg-type]
    assert result == ("image only channel", "delete")


@pytest.mark.asyncio
async def test_evaluate_image_only_allows_image() -> None:
    cog = _cog()
    config = {
        **DEFAULT_CONFIG,
        "image_only_enabled": True,
        "image_only_channel_ids": ["111"],
        "words_enabled": False,
        "spam_enabled": False,
        "duplicate_enabled": False,
        "mass_mention_enabled": False,
    }
    result = await cog.evaluate_message(
        _message(attachments=[_image()]),  # type: ignore[arg-type]
        config,
    )
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_link_only_allows_url_and_rejects_prose() -> None:
    cog = _cog()
    config = {
        **DEFAULT_CONFIG,
        "link_only_enabled": True,
        "link_only_channel_ids": ["111"],
        "words_enabled": False,
        "spam_enabled": False,
        "duplicate_enabled": False,
        "mass_mention_enabled": False,
    }
    ok = await cog.evaluate_message(
        _message(content="https://example.com"),  # type: ignore[arg-type]
        config,
    )
    bad = await cog.evaluate_message(
        _message(content="read https://example.com"),  # type: ignore[arg-type]
        config,
    )
    assert ok is None
    assert bad == ("link only channel", "delete")


@pytest.mark.asyncio
async def test_format_rules_ignore_other_channels() -> None:
    cog = _cog()
    config = {
        **DEFAULT_CONFIG,
        "image_only_enabled": True,
        "image_only_channel_ids": ["999"],
        "words_enabled": False,
        "spam_enabled": False,
        "duplicate_enabled": False,
        "mass_mention_enabled": False,
    }
    result = await cog.evaluate_message(_message(content="hello"), config)  # type: ignore[arg-type]
    assert result is None


@pytest.mark.asyncio
async def test_thread_inherits_parent_format_channel() -> None:
    cog = _cog()
    config = {
        **DEFAULT_CONFIG,
        "image_only_enabled": True,
        "image_only_channel_ids": ["111"],
        "words_enabled": False,
        "spam_enabled": False,
        "duplicate_enabled": False,
        "mass_mention_enabled": False,
    }
    result = await cog.evaluate_message(
        _message(content="hello", channel_id=222, parent_id=111),  # type: ignore[arg-type]
        config,
    )
    assert result == ("image only channel", "delete")


@pytest.mark.asyncio
async def test_claim_prevents_duplicate_apply() -> None:
    cog = _cog()
    message = _message(content="hello")
    first = await cog._claim_violation(message, "image only channel")  # type: ignore[arg-type]
    second = await cog._claim_violation(message, "image only channel")  # type: ignore[arg-type]
    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_forbidden_delete_skips_warning() -> None:
    cog = _cog()
    cog.log_automod_action = AsyncMock()  # type: ignore[method-assign]
    message = _message(content="hello")
    message.delete = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "nope"))
    message.channel.send = AsyncMock()
    await cog.apply_action(
        message,  # type: ignore[arg-type]
        "image only channel",
        "warn",
        DEFAULT_CONFIG,
    )
    message.channel.send.assert_not_called()
    cog.log_automod_action.assert_awaited()


@pytest.mark.asyncio
async def test_notfound_delete_does_not_raise() -> None:
    cog = _cog()
    cog.log_automod_action = AsyncMock()  # type: ignore[method-assign]
    message = _message(content="hello")
    message.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    await cog.apply_action(
        message,  # type: ignore[arg-type]
        "link only channel",
        "delete",
        DEFAULT_CONFIG,
    )
    cog.log_automod_action.assert_awaited()


@pytest.mark.asyncio
async def test_get_config_hydrates_on_redis_miss() -> None:
    cog = _cog()
    hydrated = {**DEFAULT_CONFIG, "enabled": True, "image_only_enabled": True}
    cog.bot.state.get_json = AsyncMock(return_value={})
    cog.bot.state._hydrate_feature_from_api = AsyncMock(return_value=hydrated)
    config = await cog.get_config(99)
    assert config["enabled"] is True
    cog.bot.state.set_json.assert_awaited()
    cog.bot.state._hydrate_feature_from_api.assert_awaited_with(99, "automod")


@pytest.mark.asyncio
async def test_image_caption_still_hits_prohibited_words() -> None:
    cog = _cog()
    config = {
        **DEFAULT_CONFIG,
        "image_only_enabled": True,
        "image_only_channel_ids": ["111"],
        "words_enabled": True,
        "prohibited_words": ["spam"],
        "word_action": "warn",
        "spam_enabled": False,
        "duplicate_enabled": False,
        "mass_mention_enabled": False,
    }
    result = await cog.evaluate_message(
        _message(content="buy spam now", attachments=[_image()]),  # type: ignore[arg-type]
        config,
    )
    assert result == ("prohibited word", "warn")
