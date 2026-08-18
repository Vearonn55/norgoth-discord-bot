"""Invite create/delete locking and one-use join attribution."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.invites import InvitesCog, invite_members_key  # noqa: E402


class _FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}

    async def hget(self, key: str, field: str) -> str | None:
        return self.hashes.get(key, {}).get(str(field))

    async def hset(self, key: str, field: str, value: str) -> int:
        self.hashes.setdefault(key, {})[str(field)] = value
        return 1

    async def get(self, key: str) -> str | None:
        return self.strings.get(key)

    async def set(self, key: str, value: str, **_kwargs: Any) -> bool:
        self.strings[key] = value
        return True

    async def delete(self, key: str) -> int:
        return 1 if self.strings.pop(key, None) is not None else 0


def _cog() -> tuple[InvitesCog, _FakeRedis]:
    redis = _FakeRedis()
    state = MagicMock()
    state.redis = redis
    state._api_base_url = ""
    state._bot_token = ""
    state.append_capped_list = AsyncMock()
    state.is_module_enabled = AsyncMock(return_value=True)
    bot = MagicMock()
    bot.state = state
    bot.get_cog = MagicMock(return_value=None)
    cog = InvitesCog(bot)
    cog._ingest_invite_lifecycle = AsyncMock()  # type: ignore[method-assign]
    cog._ingest_invite_join = AsyncMock()  # type: ignore[method-assign]
    cog._load_recent_vanished_lifecycle = AsyncMock(return_value=[])  # type: ignore[method-assign]
    return cog, redis


def _invite(*, code: str = "oneuse", max_uses: int = 1, guild_id: int = 1) -> SimpleNamespace:
    inviter = SimpleNamespace(id=99)
    inviter.__str__ = lambda self: "Bob"  # type: ignore[method-assign]
    guild = SimpleNamespace(id=guild_id)
    return SimpleNamespace(
        guild=guild,
        code=code,
        uses=0,
        max_uses=max_uses,
        max_age=0,
        temporary=False,
        inviter=inviter,
        channel=SimpleNamespace(id=5),
    )


def _member(*, guild_id: int = 1, member_id: int = 10) -> MagicMock:
    guild = MagicMock()
    guild.id = guild_id
    member = MagicMock()
    member.id = member_id
    member.bot = False
    member.guild = guild
    member.__str__ = lambda self: "Alice"  # type: ignore[method-assign]
    return member


@pytest.mark.asyncio
async def test_delete_then_join_consumed_one_use() -> None:
    cog, redis = _cog()
    invite = _invite()
    await cog.on_invite_create(invite)
    await cog.on_invite_delete(invite)
    assert "oneuse" in cog._vanished[1]
    assert "oneuse" not in cog._invite_cache.get(1, {})

    member = _member()
    cog.fetch_invite_uses = AsyncMock(return_value={})  # type: ignore[method-assign]
    inviter_id, code = await cog.attribute_join(member)
    assert code == "oneuse"
    assert inviter_id == "99"
    raw = await redis.hget(invite_members_key(1), "10")
    assert raw is not None
    record = json.loads(raw)
    assert record["attribution"] == "consumed_one_use"
    assert record["inviter_id"] == "99"
    assert "oneuse" not in cog._vanished.get(1, {})


@pytest.mark.asyncio
async def test_join_before_delete_uses_cached_one_use_meta() -> None:
    cog, _redis = _cog()
    invite = _invite()
    await cog.on_invite_create(invite)
    member = _member()
    cog.fetch_invite_uses = AsyncMock(return_value={})  # type: ignore[method-assign]
    inviter_id, code = await cog.attribute_join(member)
    assert code == "oneuse"
    assert inviter_id == "99"


@pytest.mark.asyncio
async def test_two_vanished_one_use_codes_are_ambiguous() -> None:
    cog, redis = _cog()
    await cog.on_invite_create(_invite(code="a"))
    await cog.on_invite_create(_invite(code="b"))
    await cog.on_invite_delete(_invite(code="a"))
    await cog.on_invite_delete(_invite(code="b"))
    member = _member()
    cog.fetch_invite_uses = AsyncMock(return_value={})  # type: ignore[method-assign]
    inviter_id, code = await cog.attribute_join(member)
    assert code is None
    assert inviter_id is None
    raw = await redis.hget(invite_members_key(1), "10")
    assert json.loads(raw)["attribution"] == "ambiguous"


@pytest.mark.asyncio
async def test_lifecycle_row_attributes_after_empty_memory() -> None:
    cog, redis = _cog()
    cog.fetch_invite_uses = AsyncMock(return_value={})  # type: ignore[method-assign]
    cog._load_recent_vanished_lifecycle = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "code": "oneuse",
                "inviter_id": "99",
                "inviter_name": "Bob",
                "uses": 0,
                "max_uses": 1,
                "invite_kind": "one_use",
                "status": "consumed",
            }
        ]
    )
    member = _member()
    inviter_id, code = await cog.attribute_join(member)
    assert code == "oneuse"
    assert inviter_id == "99"
    record = json.loads(await redis.hget(invite_members_key(1), "10"))
    assert record["attribution"] == "consumed_one_use"


@pytest.mark.asyncio
async def test_duplicate_join_is_idempotent() -> None:
    cog, _redis = _cog()
    await cog.on_invite_create(_invite())
    member = _member()
    cog.fetch_invite_uses = AsyncMock(return_value={})  # type: ignore[method-assign]
    first = await cog.attribute_join(member)
    cog.fetch_invite_uses = AsyncMock(side_effect=AssertionError("should not refetch"))
    second = await cog.attribute_join(member)
    assert first == second


@pytest.mark.asyncio
async def test_manual_delete_without_join_does_not_credit() -> None:
    cog, redis = _cog()
    await cog.on_invite_create(_invite())
    await cog.on_invite_delete(_invite())
    assert await redis.hget(invite_members_key(1), "10") is None
    assert cog._vanished[1]["oneuse"]["inviter_id"] == "99"
