"""Smoke coverage for Invite Logging emission paths (mocked Discord + Redis).

Covers attribution join/leave emission, vanity, unknown, module-off gate,
and per-event_type routing — without custom Invite Log Messaging templates.
"""

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

from bot.invites import (  # noqa: E402
    InvitesCog,
    invite_counters_key,
    invite_members_key,
)
from bot.server_logging import ServerLoggingCog  # noqa: E402


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


def _make_member(*, guild_id: int = 1, member_id: int = 10, name: str = "Alice") -> MagicMock:
    guild = MagicMock()
    guild.id = guild_id
    guild.name = "Dummy Guild"
    guild.get_member = MagicMock(return_value=MagicMock())

    member = MagicMock()
    member.id = member_id
    member.bot = False
    member.guild = guild
    member.name = name
    member.__str__ = lambda self: f"{name}#{member_id}"  # type: ignore[method-assign]
    return member


def _build_cog(*, module_on: bool = True) -> tuple[InvitesCog, _FakeRedis, AsyncMock]:
    redis = _FakeRedis()
    state = MagicMock()
    state.redis = redis
    state.is_module_enabled = AsyncMock(return_value=module_on)
    state.get_json = AsyncMock(side_effect=lambda key: json.loads(redis.strings[key]) if key in redis.strings else None)

    logging_cog = MagicMock()
    logging_cog.record_event = AsyncMock()

    bot = MagicMock()
    bot.state = state
    bot.get_cog = MagicMock(return_value=logging_cog)

    cog = InvitesCog(bot)
    return cog, redis, logging_cog.record_event


@pytest.mark.asyncio
async def test_smoke_attributed_join_emits_once() -> None:
    cog, redis, record_event = _build_cog()
    member = _make_member()
    guild_id = member.guild.id

    await redis.hset(
        invite_members_key(guild_id),
        str(member.id),
        json.dumps(
            {
                "inviter_id": "99",
                "inviter_name": "Bob",
                "code": "abc12",
                "joined_at": "2026-08-09T12:00:00+00:00",
                "member_name": "Alice",
            }
        ),
    )
    await redis.hset(
        invite_counters_key(guild_id),
        "99",
        json.dumps({"name": "Bob", "joins": 3, "leaves": 1, "rejoins": 0}),
    )
    cog.attribute_join = AsyncMock(return_value=("99", "abc12"))  # type: ignore[method-assign]

    await cog.on_member_join(member)

    assert record_event.await_count == 1
    args, kwargs = record_event.await_args
    assert args[1] == "invites"
    assert kwargs["event_type"] == "invite_member_joined"
    fields = args[4]
    assert fields["Invited By"] == "<@99>"
    assert fields["Inviter Total Invites"] == "2"  # net = 3-1
    assert fields["Attribution"] == "attributed"


@pytest.mark.asyncio
async def test_smoke_leave_uses_original_inviter_and_net() -> None:
    cog, redis, record_event = _build_cog()
    member = _make_member()
    guild_id = member.guild.id

    await redis.hset(
        invite_members_key(guild_id),
        str(member.id),
        json.dumps(
            {
                "inviter_id": "99",
                "inviter_name": "Bob",
                "code": "abc12",
                "joined_at": "2026-08-09T12:00:00+00:00",
                "member_name": "Alice",
            }
        ),
    )
    await redis.hset(
        invite_counters_key(guild_id),
        "99",
        json.dumps({"name": "Bob", "joins": 3, "leaves": 0, "rejoins": 0}),
    )

    await cog.on_member_remove(member)

    assert record_event.await_count == 1
    args, kwargs = record_event.await_args
    assert kwargs["event_type"] == "invite_member_left"
    fields = args[4]
    assert fields["Original Inviter"] == "<@99>"
    # leave bumps leaves before logging, so net becomes 3-1 = 2
    assert fields["Inviter Total Invites"] == "2"
    assert fields["Attribution"] == "attributed"

    raw = await redis.hget(invite_counters_key(guild_id), "99")
    assert json.loads(raw)["leaves"] == 1


@pytest.mark.asyncio
async def test_smoke_vanity_and_unknown() -> None:
    cog, _redis, record_event = _build_cog()
    guild = _make_member().guild

    await cog._log_invite_event(
        guild,
        kind="join",
        event_type="invite_member_joined",
        action="Member joined via invite",
        member_id="10",
        member_name="Alice",
        member_username="alice",
        inviter_id=None,
        inviter_name=None,
        invite_code="vanity",
        joined_at=None,
    )
    fields = record_event.await_args.args[4]
    assert fields["Invited By"] == "Vanity URL"
    assert fields["Attribution"] == "vanity"

    record_event.reset_mock()
    await cog._log_invite_event(
        guild,
        kind="leave",
        event_type="invite_member_left",
        action="Member left — invite attribution",
        member_id="10",
        member_name="Alice",
        member_username="alice",
        inviter_id=None,
        inviter_name=None,
        invite_code=None,
        joined_at=None,
        left_at="2026-08-09T13:00:00+00:00",
    )
    fields = record_event.await_args.args[4]
    assert fields["Original Inviter"] == "Unknown"
    assert fields["Attribution"] == "unknown"
    assert "null" not in json.dumps(fields).lower()


@pytest.mark.asyncio
async def test_smoke_module_off_skips_emit() -> None:
    cog, redis, record_event = _build_cog(module_on=False)
    member = _make_member()
    cog.attribute_join = AsyncMock(return_value=("99", "abc12"))  # type: ignore[method-assign]

    await cog.on_member_join(member)
    assert record_event.await_count == 0

    await redis.hset(
        invite_members_key(member.guild.id),
        str(member.id),
        json.dumps(
            {
                "inviter_id": "99",
                "inviter_name": "Bob",
                "code": "abc12",
                "joined_at": "2026-08-09T12:00:00+00:00",
                "member_name": "Alice",
            }
        ),
    )
    await cog.on_member_remove(member)
    assert record_event.await_count == 0
    # leave still closes the Redis record for idempotency
    raw = await redis.hget(invite_members_key(member.guild.id), str(member.id))
    assert json.loads(raw).get("left_at")


@pytest.mark.asyncio
async def test_smoke_join_leave_route_to_different_channels() -> None:
    """ServerLoggingCog.route_event resolves channel per event_type."""

    class _FakeTextChannel:
        def __init__(self) -> None:
            self.send = AsyncMock()

    redis = _FakeRedis()
    snapshot = {
        "enabled": True,
        "events": {
            "invite_member_joined": {"channel_id": "111", "color": 5763719},
            "invite_member_left": {"channel_id": "222", "color": 5763719},
        },
    }
    await redis.set(
        "norgoth:guild:1:logging:routing",
        json.dumps(snapshot),
    )

    state = MagicMock()
    state.redis = redis
    state.is_module_enabled = AsyncMock(return_value=True)
    state.get_json = AsyncMock(
        side_effect=lambda key: json.loads(redis.strings[key])
        if key in redis.strings
        else None
    )
    state.append_capped_list = AsyncMock()

    bot = MagicMock()
    bot.state = state
    logging_cog = ServerLoggingCog(bot)

    join_ch = _FakeTextChannel()
    leave_ch = _FakeTextChannel()

    guild = MagicMock()
    guild.id = 1
    guild.get_channel = MagicMock(
        side_effect=lambda cid: join_ch
        if cid == 111
        else leave_ch
        if cid == 222
        else None
    )
    guild.fetch_channel = AsyncMock(side_effect=AssertionError("should not fetch"))

    with patch("bot.server_logging.discord.TextChannel", _FakeTextChannel):
        await logging_cog.record_event(
            guild,
            "invites",
            "Member joined via invite",
            "join body",
            {"Event": "Member Joined"},
            event_type="invite_member_joined",
            actor_id="10",
            actor_name="Alice",
        )
        await logging_cog.record_event(
            guild,
            "invites",
            "Member left — invite attribution",
            "leave body",
            {"Event": "Member Left"},
            event_type="invite_member_left",
            actor_id="10",
            actor_name="Alice",
        )

    assert join_ch.send.await_count == 1
    assert leave_ch.send.await_count == 1
    assert join_ch.send.await_args.kwargs["embed"].description == "join body"
    assert leave_ch.send.await_args.kwargs["embed"].description == "leave body"


@pytest.mark.asyncio
async def test_smoke_route_fetches_on_cache_miss() -> None:
    class _FakeTextChannel:
        def __init__(self) -> None:
            self.send = AsyncMock()

    redis = _FakeRedis()
    await redis.set(
        "norgoth:guild:1:logging:routing",
        json.dumps(
            {
                "enabled": True,
                "events": {
                    "invite_member_joined": {"channel_id": "111", "color": 5763719},
                },
            }
        ),
    )
    state = MagicMock()
    state.redis = redis
    state.is_module_enabled = AsyncMock(return_value=True)
    state.get_json = AsyncMock(
        side_effect=lambda key: json.loads(redis.strings[key])
        if key in redis.strings
        else None
    )
    state.append_capped_list = AsyncMock()
    bot = MagicMock()
    bot.state = state
    logging_cog = ServerLoggingCog(bot)

    channel = _FakeTextChannel()
    guild = MagicMock()
    guild.id = 1
    guild.get_channel = MagicMock(return_value=None)
    guild.fetch_channel = AsyncMock(return_value=channel)

    with patch("bot.server_logging.discord.TextChannel", _FakeTextChannel):
        ok = await logging_cog.route_event(
            guild,
            "invite_member_joined",
            "invites",
            "title",
            "body",
            {},
        )
    assert ok is True
    guild.fetch_channel.assert_awaited_once_with(111)
    assert channel.send.await_count == 1


@pytest.mark.asyncio
async def test_smoke_unmapped_invite_event_does_not_send() -> None:
    redis = _FakeRedis()
    await redis.set(
        "norgoth:guild:1:logging:routing",
        json.dumps({"enabled": True, "events": {"member_join": {"channel_id": "1"}}}),
    )
    state = MagicMock()
    state.redis = redis
    state.is_module_enabled = AsyncMock(return_value=True)
    state.get_json = AsyncMock(
        side_effect=lambda key: json.loads(redis.strings[key])
        if key in redis.strings
        else {}
    )
    state.append_capped_list = AsyncMock()
    # legacy config also empty for invites
    bot = MagicMock()
    bot.state = state
    logging_cog = ServerLoggingCog(bot)
    logging_cog.get_config = AsyncMock(return_value={"enabled": True})  # type: ignore[method-assign]

    guild = MagicMock()
    guild.id = 1
    ok = await logging_cog.route_event(
        guild,
        "invite_member_joined",
        "invites",
        "title",
        "body",
        {},
    )
    assert ok is False

