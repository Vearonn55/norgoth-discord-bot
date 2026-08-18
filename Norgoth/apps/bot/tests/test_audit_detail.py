"""Unit tests for versioned channel/role/thread audit diffs."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import Object, PermissionOverwrite, Permissions, Role, User

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.audit_detail import (  # noqa: E402
    SCHEMA_VERSION,
    build_channel_update_detail,
    build_role_update_detail,
    build_thread_update_detail,
    discord_embed_field_changes,
)
from bot.permission_diff import (  # noqa: E402
    diff_channel_overwrite_items,
    diff_role_permission_flags,
)
from bot.server_logging import ServerLoggingCog  # noqa: E402


def _role_target(role_id: int = 10, name: str = "Mods") -> Object:
    target = Object(id=role_id, type=Role)
    target.name = name  # type: ignore[attr-defined]
    return target


def _member_target(user_id: int = 20, name: str = "Alice") -> Object:
    target = Object(id=user_id, type=User)
    target.name = name  # type: ignore[attr-defined]
    return target


def _channel(**kwargs):
    defaults = {
        "overwrites": {},
        "name": "general",
        "id": 99,
        "permissions_synced": False,
        "category": None,
        "topic": "hello",
        "type": "text",
        "guild": SimpleNamespace(id=1),
        "parent_id": None,
        "position": 1,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _role(
    *,
    name: str = "Mods",
    role_id: int = 5,
    permissions: Permissions | None = None,
    color: int = 0,
    hoist: bool = False,
    mentionable: bool = False,
    unicode_emoji: str | None = None,
    display_icon: str | None = None,
    position: int = 1,
):
    guild = SimpleNamespace(id=77)
    return SimpleNamespace(
        name=name,
        id=role_id,
        permissions=permissions or Permissions.none(),
        guild=guild,
        colour=SimpleNamespace(value=color),
        hoist=hoist,
        mentionable=mentionable,
        unicode_emoji=unicode_emoji,
        display_icon=display_icon,
        position=position,
    )


def test_channel_name_and_topic_changes() -> None:
    before = _channel(name="old", topic="one")
    after = _channel(name="new", topic="two")
    detail = build_channel_update_detail(before, after)
    by_field = {item.field: item for item in detail.field_changes}
    assert by_field["name"].previous == "old"
    assert by_field["name"].next == "new"
    assert by_field["topic"].previous == "one"
    assert by_field["topic"].next == "two"
    assert detail.to_dict()["schema_version"] == SCHEMA_VERSION


def test_channel_multiple_fields_and_omits_unchanged() -> None:
    before = _channel(name="general", nsfw=False, slowmode_delay=0, position=1)
    after = _channel(name="general", nsfw=True, slowmode_delay=10, position=1)
    detail = build_channel_update_detail(before, after)
    fields = {item.field for item in detail.field_changes}
    assert fields == {"nsfw", "slowmode_delay"}


def test_channel_missing_attrs_are_skipped() -> None:
    before = _channel(name="a")
    after = _channel(name="b")
    detail = build_channel_update_detail(before, after)
    fields = {item.field for item in detail.field_changes}
    assert fields == {"name"}
    assert "nsfw" not in fields
    assert "bitrate" not in fields


def test_empty_topic_and_none_are_equivalent() -> None:
    before = _channel(topic=None)
    after = _channel(topic="")
    detail = build_channel_update_detail(before, after)
    assert all(item.field != "topic" for item in detail.field_changes)


def test_parent_change_uses_id_and_name() -> None:
    before = _channel(
        parent_id=1,
        category=SimpleNamespace(name="Old"),
    )
    after = _channel(
        parent_id=2,
        category=SimpleNamespace(name="New"),
    )
    detail = build_channel_update_detail(before, after)
    parent = next(item for item in detail.field_changes if item.field == "parent")
    assert parent.previous == {"id": "1", "name": "Old"}
    assert parent.next == {"id": "2", "name": "New"}


def test_reordered_overwrites_do_not_diff() -> None:
    role_a = _role_target(10, "A")
    role_b = _role_target(11, "B")
    ow_a = PermissionOverwrite(view_channel=True)
    ow_b = PermissionOverwrite(send_messages=False)
    before = _channel(overwrites={role_a: ow_a, role_b: ow_b})
    after = _channel(overwrites={role_b: ow_b, role_a: ow_a})
    assert diff_channel_overwrite_items(before, after) == []
    assert build_channel_update_detail(before, after).is_empty()


def test_overwrite_all_six_transitions_structured() -> None:
    role = _role_target()
    before = _channel(
        overwrites={
            role: PermissionOverwrite(
                view_channel=True, send_messages=False, attach_files=None
            )
        }
    )
    after = _channel(
        overwrites={
            role: PermissionOverwrite(
                view_channel=False,
                send_messages=True,
                attach_files=True,
                embed_links=False,
            )
        }
    )
    other = _role_target(11, "Helpers")
    before.overwrites[other] = PermissionOverwrite(
        view_channel=True, send_messages=False
    )
    after.overwrites[other] = PermissionOverwrite(
        view_channel=None, send_messages=None
    )

    items = diff_channel_overwrite_items(before, after)
    pairs = {(item.permission, item.previous, item.next) for item in items}
    assert ("view_channel", "allow", "deny") in pairs
    assert ("send_messages", "deny", "allow") in pairs
    assert ("attach_files", "inherit", "allow") in pairs
    assert ("embed_links", "inherit", "deny") in pairs
    assert ("view_channel", "allow", "inherit") in pairs
    assert ("send_messages", "deny", "inherit") in pairs
    inherit_to_from_deny = [
        item
        for item in items
        if item.previous == "deny" and item.next == "inherit"
    ]
    assert inherit_to_from_deny
    assert all(item.change == "transition" for item in inherit_to_from_deny)


def test_overwrite_added_and_removed_structured() -> None:
    role = _role_target()
    member = _member_target()
    before = _channel(overwrites={role: PermissionOverwrite(view_channel=False)})
    after = _channel(overwrites={member: PermissionOverwrite(view_channel=True)})
    items = diff_channel_overwrite_items(before, after)
    added = [item for item in items if item.change == "overwrite_added"]
    removed = [item for item in items if item.change == "overwrite_removed"]
    assert len(added) == 1
    assert added[0].target_kind == "member"
    assert added[0].permission == "view_channel"
    assert added[0].previous == "inherit"
    assert added[0].next == "allow"
    assert len(removed) == 1
    assert removed[0].target_kind == "role"
    assert removed[0].previous == "deny"
    assert removed[0].next == "inherit"


def test_inherit_only_overwrite_not_listed() -> None:
    role = _role_target()
    before = _channel(overwrites={})
    after = _channel(overwrites={role: PermissionOverwrite()})
    assert diff_channel_overwrite_items(before, after) == []


def test_role_name_color_mentionable() -> None:
    before = _role(name="Old", color=1, mentionable=False, hoist=False)
    after = _role(name="New", color=2, mentionable=True, hoist=False)
    detail = build_role_update_detail(before, after)
    by_field = {item.field: item for item in detail.field_changes}
    assert set(by_field) == {"name", "color", "mentionable"}
    assert by_field["color"].previous == 1
    assert by_field["color"].next == 2
    assert "hoist" not in by_field


def test_role_permissions_granted_revoked_flag_ids() -> None:
    before = _role(permissions=Permissions(send_messages=True))
    after = _role(permissions=Permissions(manage_channels=True))
    flags = diff_role_permission_flags(before.permissions, after.permissions)
    assert "manage_channels" in flags.granted
    assert "send_messages" in flags.revoked
    assert "view_channel" not in flags.granted
    detail = build_role_update_detail(before, after)
    assert detail.permission_changes is not None
    granted = [item["permission"] for item in detail.permission_changes["granted"]]
    revoked = [item["permission"] for item in detail.permission_changes["revoked"]]
    assert granted == ["manage_channels"]
    assert revoked == ["send_messages"]


def test_unknown_permission_bits_remain() -> None:
    known_mask = 0
    for bit in Permissions.VALID_FLAGS.values():
        known_mask |= bit
    leftover = 0
    for shift in range(63, -1, -1):
        candidate = 1 << shift
        if not (known_mask & candidate):
            leftover = candidate
            break
    assert leftover
    before = Permissions(send_messages=True)
    after = Permissions(before.value | leftover)
    flags = diff_role_permission_flags(before, after)
    assert flags.granted_unknown_mask == leftover
    detail = build_role_update_detail(
        _role(permissions=before),
        _role(permissions=after),
    )
    unknown = [
        item
        for item in detail.permission_changes["granted"]
        if item["permission"] == "unknown"
    ]
    assert unknown
    assert unknown[0]["unknown_mask"].startswith("0x")


def test_thread_archived_locked() -> None:
    before = SimpleNamespace(
        id=1,
        name="t",
        archived=False,
        locked=False,
        auto_archive_duration=60,
        type="public_thread",
    )
    after = SimpleNamespace(
        id=1,
        name="t",
        archived=True,
        locked=True,
        auto_archive_duration=60,
        type="public_thread",
    )
    detail = build_thread_update_detail(before, after)
    fields = {item.field: item.next for item in detail.field_changes}
    assert fields["archived"] is True
    assert fields["locked"] is True
    assert "auto_archive_duration" not in fields
    assert detail.target["kind"] == "thread"


def test_embed_fields_use_actual_topic_not_updated_token() -> None:
    before = _channel(topic="old topic")
    after = _channel(topic="new topic")
    detail = build_channel_update_detail(before, after)
    fields = discord_embed_field_changes(detail.field_changes)
    assert fields["Topic"] == "old topic → new topic"
    assert "updated" not in fields["Topic"]


def _logging_cog() -> tuple[ServerLoggingCog, AsyncMock]:
    state = MagicMock()
    state.is_module_enabled = AsyncMock(return_value=True)
    state.append_capped_list = AsyncMock()
    state.get_json = AsyncMock(return_value=None)
    state._api_base_url = ""
    state._bot_token = ""
    bot = MagicMock()
    bot.state = state
    cog = ServerLoggingCog(bot)
    cog.route_event = AsyncMock(return_value=[])
    return cog, state.append_capped_list


@pytest.mark.asyncio
async def test_role_update_single_event_includes_structured_detail() -> None:
    cog, append = _logging_cog()
    cog._resolve_audit_actor_detailed = AsyncMock(
        return_value=("8", "Mod", "found", "cleanup")
    )
    before = _role(name="Old", permissions=Permissions(send_messages=True))
    after = _role(name="New", permissions=Permissions(manage_channels=True))
    after.guild = before.guild
    await cog.on_guild_role_update(before, after)
    assert append.await_count == 1
    entry = append.await_args.args[1]
    assert entry["action"] == "Role updated"
    assert "Manage Channels" in entry["fields"]["Granted"]
    assert "Name" in entry["fields"]


@pytest.mark.asyncio
async def test_channel_update_persists_detail_before_embed_packing() -> None:
    cog, append = _logging_cog()
    cog._ingest_server_event = AsyncMock()
    cog._resolve_audit_actor_detailed = AsyncMock(
        return_value=(None, None, "unavailable", None)
    )
    role = _role_target()
    before = _channel(overwrites={}, topic="old")
    after = _channel(
        overwrites={role: PermissionOverwrite(view_channel=True)},
        topic="brand new topic text",
    )
    after.guild = SimpleNamespace(id=42)
    await cog.on_guild_channel_update(before, after)
    ingest = cog._ingest_server_event
    ingest.assert_awaited()
    detail = ingest.await_args.args[2]
    assert not detail.is_empty()
    topic = next(item for item in detail.field_changes if item.field == "topic")
    assert topic.next == "brand new topic text"
    perms = detail.permission_changes
    assert perms["kind"] == "overwrites"
    assert perms["items"][0]["permission"] == "view_channel"
    assert append.await_count == 1
