"""Honeypot warning post/pin is idempotent and persists IDs before pin."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import discord
import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.honeypot import (  # noqa: E402
    HoneypotCog,
    is_duplicate_warning,
    missing_warning_permissions,
)


BOT_ID = 99
CHANNEL_ID = 10
OLD_CHANNEL_ID = 11
MESSAGE_ID = 555


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        _ = ex
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


def _http_error(status: int, cls: type[discord.HTTPException] = discord.HTTPException):
    response = SimpleNamespace(status=status, reason="ERR", headers={})
    return cls(response, {"message": "err"})


def _perms(**overrides: bool) -> SimpleNamespace:
    values = {
        "view_channel": True,
        "send_messages": True,
        "read_message_history": True,
        "manage_messages": True,
        "pin_messages": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _message(
    message_id: int = MESSAGE_ID,
    *,
    author_id: int = BOT_ID,
    pinned: bool = False,
    content: str = "warn",
    title: str | None = None,
) -> SimpleNamespace:
    embeds = [SimpleNamespace(title=title)] if title else []
    return SimpleNamespace(
        id=message_id,
        author=SimpleNamespace(id=author_id),
        pinned=pinned,
        content=content,
        embeds=embeds,
        edit=AsyncMock(),
        pin=AsyncMock(),
        unpin=AsyncMock(),
        delete=AsyncMock(),
    )


async def _empty_history(limit: int = 50):
    _ = limit
    if False:
        yield None


def _channel(
    *,
    channel_id: int = CHANNEL_ID,
    existing: Any = None,
    fetch_error: Exception | None = None,
    send_message: Any | None = None,
    pin_error: Exception | None = None,
    extras: list[Any] | None = None,
    perms: SimpleNamespace | None = None,
) -> Mock:
    channel = Mock(spec=discord.TextChannel)
    channel.id = channel_id
    posted = send_message or _message()
    if pin_error:
        posted.pin = AsyncMock(side_effect=pin_error)

    async def fetch_message(_message_id: int):
        if fetch_error:
            raise fetch_error
        if existing is None:
            raise _http_error(404, discord.NotFound)
        return existing

    channel.fetch_message = AsyncMock(side_effect=fetch_message)
    channel.send = AsyncMock(return_value=posted)
    channel.pins = AsyncMock(return_value=[posted, *(extras or [])] if extras else [posted])
    channel.history = lambda limit=50: _empty_history(limit)
    channel.permissions_for = lambda _me: perms or _perms()
    return channel


def _cog(channel: Mock, channels: dict[int, Mock] | None = None) -> HoneypotCog:
    redis = FakeRedis()
    saved: list[dict[str, Any]] = []

    async def persist(guild_id: int, feature_key: str, config: dict[str, Any], enabled=None):
        _ = guild_id, feature_key, enabled
        saved.append(dict(config))

    bot = SimpleNamespace(
        state=SimpleNamespace(redis=redis, persist_feature_config=persist),
    )
    cog = object.__new__(HoneypotCog)
    cog.bot = bot  # type: ignore[assignment]
    cog._saved = saved  # type: ignore[attr-defined]
    mapping = channels or {channel.id: channel}

    guild = SimpleNamespace(
        id=1,
        me=SimpleNamespace(id=BOT_ID),
        get_channel=lambda cid: mapping.get(int(cid)),
    )
    cog._guild = guild  # type: ignore[attr-defined]
    cog._channel = channel  # type: ignore[attr-defined]
    return cog


@pytest.mark.asyncio
async def test_first_post_persists_id_even_if_pin_fails() -> None:
    pin_error = _http_error(403, discord.Forbidden)
    posted = _message()
    posted.pin = AsyncMock(side_effect=pin_error)
    channel = _channel(existing=None, send_message=posted, pin_error=pin_error)
    cog = _cog(channel)
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_content": "warn",
    }
    result = await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    assert channel.send.await_count == 1
    assert result["warning_message_id"] == str(MESSAGE_ID)
    assert result["warning_pinned"] is False
    assert result["warning_status"]["code"] == "pin_failed"
    assert cog._saved[-1]["warning_message_id"] == str(MESSAGE_ID)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_existing_message_is_edited_not_reposted() -> None:
    existing = _message(pinned=True)
    channel = _channel(existing=existing)
    cog = _cog(channel)
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_message_id": str(MESSAGE_ID),
        "warning_channel_id": str(CHANNEL_ID),
        "warning_content": "warn",
    }
    await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    assert channel.send.await_count == 0
    existing.edit.assert_awaited()


@pytest.mark.asyncio
async def test_404_restores_one_replacement() -> None:
    channel = _channel(existing=None, fetch_error=_http_error(404, discord.NotFound))
    cog = _cog(channel)
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_message_id": "111",
        "warning_channel_id": str(CHANNEL_ID),
        "warning_content": "warn",
        "force_warning_repost": False,
    }
    result = await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    assert channel.send.await_count == 1
    assert result["warning_message_id"] == str(MESSAGE_ID)


@pytest.mark.asyncio
async def test_403_fetch_does_not_send() -> None:
    channel = _channel(fetch_error=_http_error(403, discord.Forbidden))
    cog = _cog(channel)
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_message_id": "111",
        "warning_channel_id": str(CHANNEL_ID),
        "warning_content": "warn",
        "force_warning_repost": True,
    }
    await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    assert channel.send.await_count == 0


@pytest.mark.asyncio
async def test_lock_prevents_concurrent_send() -> None:
    channel = _channel(existing=None)
    cog = _cog(channel)
    await cog.bot.state.redis.set(  # type: ignore[attr-defined]
        f"norgoth:guild:1:honeypot:warning-lock", "1", nx=True, ex=120
    )
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_content": "warn",
    }
    await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    assert channel.send.await_count == 0


@pytest.mark.asyncio
async def test_channel_change_deletes_old_and_posts_new() -> None:
    old_message = _message(message_id=1, pinned=True)
    old_channel = _channel(channel_id=OLD_CHANNEL_ID, existing=old_message)
    new_channel = _channel(channel_id=CHANNEL_ID, existing=None)
    cog = _cog(new_channel, channels={OLD_CHANNEL_ID: old_channel, CHANNEL_ID: new_channel})
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_message_id": "1",
        "warning_channel_id": str(OLD_CHANNEL_ID),
        "warning_content": "warn",
        "punishment": "kick",
    }
    result = await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    old_message.delete.assert_awaited()
    assert new_channel.send.await_count == 1
    assert result["warning_channel_id"] == str(CHANNEL_ID)
    assert result["punishment"] == "kick"


@pytest.mark.asyncio
async def test_duplicate_pinned_bot_warnings_are_deleted() -> None:
    canonical = _message(message_id=MESSAGE_ID, pinned=True)
    extra = _message(message_id=777, pinned=True, content="warn")
    channel = _channel(existing=canonical, extras=[extra])
    cog = _cog(channel)
    config = {
        "post_pinned_warning": True,
        "trap_channel_ids": [str(CHANNEL_ID)],
        "warning_message_id": str(MESSAGE_ID),
        "warning_channel_id": str(CHANNEL_ID),
        "warning_content": "warn",
    }
    await cog.ensure_pinned_warning(cog._guild, config)  # type: ignore[attr-defined]
    extra.delete.assert_awaited()
    canonical.delete.assert_not_called()


def test_missing_permissions_lists_pin_and_history() -> None:
    missing = missing_warning_permissions(
        _perms(send_messages=True, manage_messages=False, pin_messages=False, read_message_history=False)
    )
    assert "manage_messages" in missing
    assert "read_message_history" in missing


def test_duplicate_matcher_skips_canonical_and_users() -> None:
    canonical = _message(message_id=1, pinned=True)
    user = _message(message_id=2, author_id=5, pinned=True)
    extra = _message(message_id=3, pinned=True)
    assert is_duplicate_warning(
        canonical, me_id=BOT_ID, canonical_id="1", content="warn", embed_title=None
    ) is False
    assert is_duplicate_warning(
        user, me_id=BOT_ID, canonical_id="1", content="warn", embed_title=None
    ) is False
    assert is_duplicate_warning(
        extra, me_id=BOT_ID, canonical_id="1", content="warn", embed_title=None
    ) is True
