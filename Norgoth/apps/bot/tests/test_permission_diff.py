"""Unit tests for role/channel permission diffs and audit-actor correlation."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import Object, PermissionOverwrite, Permissions, Role, User

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.logging_presentation import compose_log_embed_spec  # noqa: E402
from bot.permission_diff import (  # noqa: E402
    channel_overwrite_fields,
    diff_channel_overwrites,
    diff_role_permissions,
    pack_section_lines,
    role_permission_fields,
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


def _channel(
    *,
    overwrites: dict | None = None,
    name: str = "general",
    channel_id: int = 99,
    permissions_synced: bool = False,
    category: object | None = None,
    topic: str | None = "hello",
    channel_type: str = "text",
):
    return SimpleNamespace(
        overwrites=overwrites or {},
        name=name,
        id=channel_id,
        permissions_synced=permissions_synced,
        category=category,
        topic=topic,
        type=channel_type,
        guild=SimpleNamespace(id=1),
    )


def test_role_permission_grant_and_revoke() -> None:
    before = Permissions(send_messages=True, manage_channels=False)
    after = Permissions(send_messages=False, manage_channels=True)
    diff = diff_role_permissions(before, after)
    assert "Manage Channels" in diff.granted
    assert "Send Messages" in diff.revoked
    assert "View Channel" not in diff.granted
    assert "View Channel" not in diff.revoked


def test_role_permission_multiple_flags() -> None:
    before = Permissions.none()
    after = Permissions(kick_members=True, ban_members=True, manage_guild=True)
    diff = diff_role_permissions(before, after)
    assert diff.granted == (
        "Ban Members",
        "Kick Members",
        "Manage Guild",
    )
    assert diff.revoked == ()


def test_role_permission_unknown_future_bits() -> None:
    known = Permissions(send_messages=True)
    unknown_bit = 1 << 50
    # 1<<50 might already be a known flag; pick a bit outside VALID_FLAGS
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
    after = Permissions(known.value | leftover)
    diff = diff_role_permissions(known, after)
    assert any(label.startswith("Unknown permission (0x") for label in diff.granted)
    assert "Send Messages" not in diff.granted


def test_overwrite_all_allow_deny_inherit_transitions() -> None:
    role = _role_target()
    before = _channel(
        overwrites={
            role: PermissionOverwrite(view_channel=True, send_messages=False, attach_files=None)
        }
    )
    after = _channel(
        overwrites={
            role: PermissionOverwrite(
                view_channel=False,  # Allow → Deny
                send_messages=True,  # Deny → Allow
                attach_files=True,  # Inherit → Allow
                embed_links=False,  # Inherit → Deny
            )
        }
    )
    # Also Allow → Inherit and Deny → Inherit via a second role
    other = _role_target(11, "Helpers")
    before.overwrites[other] = PermissionOverwrite(view_channel=True, send_messages=False)
    after.overwrites[other] = PermissionOverwrite(view_channel=None, send_messages=None)

    diff = diff_channel_overwrites(before, after)
    granted_text = "\n".join(diff.granted)
    denied_text = "\n".join(diff.denied)
    inherited_text = "\n".join(diff.inherited)
    assert "Send Messages (Deny → Allow)" in granted_text
    assert "Attach Files (Inherit → Allow)" in granted_text
    assert "View Channel (Allow → Deny)" in denied_text
    assert "Embed Links (Inherit → Deny)" in denied_text
    assert "View Channel (Allow → Inherit)" in inherited_text
    assert "Send Messages (Deny → Inherit)" in inherited_text
    assert "granted" not in inherited_text.lower() or "Deny → Inherit" in inherited_text
    assert not any("granted" in line.lower() and "Inherit" in line for line in diff.inherited)


def test_overwrite_added_and_removed() -> None:
    role = _role_target()
    member = _member_target()
    before = _channel(
        overwrites={role: PermissionOverwrite(view_channel=False)},
    )
    after = _channel(
        overwrites={member: PermissionOverwrite(view_channel=True)},
    )
    diff = diff_channel_overwrites(before, after)
    assert len(diff.removed) == 1
    assert "Deny View Channel" in diff.removed[0]
    assert "@Mods" in diff.removed[0]
    assert len(diff.added) == 1
    assert "Allow View Channel" in diff.added[0]
    assert "Alice" in diff.added[0]


def test_category_sync_detection() -> None:
    role = _role_target()
    synced = {role: PermissionOverwrite(view_channel=True)}
    category = SimpleNamespace(overwrites=synced)
    before = _channel(
        overwrites={role: PermissionOverwrite(send_messages=False)},
        permissions_synced=False,
        category=category,
    )
    after = _channel(
        overwrites=synced,
        permissions_synced=True,
        category=category,
    )
    diff = diff_channel_overwrites(before, after)
    assert diff.category_synced is True
    fields = channel_overwrite_fields(diff)
    assert fields["Sync"] == "permissions synchronized with category"


def test_role_fields_omit_unchanged_and_pack() -> None:
    diff = diff_role_permissions(
        Permissions(administrator=True),
        Permissions(administrator=True, manage_channels=True),
    )
    fields = role_permission_fields(diff)
    assert "Administrator" not in fields.get("Granted", "")
    assert "Manage Channels" in fields["Granted"]
    assert "Revoked" not in fields


def test_large_diff_stays_within_embed_limits() -> None:
    lines = [f"@Mods (role 1): Permission {index} (Inherit → Allow)" for index in range(80)]
    packed = pack_section_lines("Granted", lines, max_parts=2)
    spec = compose_log_embed_spec(
        "Channel updated",
        "Channel **#general** was updated.",
        fields={
            "Channel": "#general",
            "Channel ID": "99",
            **packed,
        },
        footer="NorBot · channel event",
        event_type="channel_update",
    )
    total = len(spec["title"]) + len(spec["description"]) + len(spec["footer"] or "")
    for name, value, _inline in spec["fields"]:
        assert value
        assert len(value) <= 1024
        total += len(name) + len(value)
    assert total <= 6000
    assert len(spec["fields"]) <= 20
    joined = " ".join(value for _n, value, _i in spec["fields"])
    assert "Permission 0" in joined
    assert "and" in joined and "more" in joined


def test_granted_fields_are_not_inline() -> None:
    spec = compose_log_embed_spec(
        "Role permissions updated",
        "Permissions changed.",
        fields={"Granted": "Manage Channels", "Role ID": "1"},
        event_type="role_update",
    )
    by_name = {name: inline for name, _value, inline in spec["fields"]}
    assert by_name["Granted"] is False
    assert by_name["Role ID"] is True


def _logging_cog(*, module_on: bool = True) -> tuple[ServerLoggingCog, AsyncMock]:
    state = MagicMock()
    state.is_module_enabled = AsyncMock(return_value=module_on)
    state.append_capped_list = AsyncMock()
    state.get_json = AsyncMock(return_value=None)
    state._api_base_url = ""
    state._bot_token = ""
    bot = MagicMock()
    bot.state = state
    cog = ServerLoggingCog(bot)
    cog.route_event = AsyncMock(return_value=True)
    return cog, state.append_capped_list


def _fake_role(*, name: str, permissions: Permissions, role_id: int = 5) -> MagicMock:
    guild = MagicMock()
    guild.id = 77
    role = MagicMock()
    role.name = name
    role.id = role_id
    role.permissions = permissions
    role.guild = guild
    return role


@pytest.mark.asyncio
async def test_role_update_logs_rename_and_permissions() -> None:
    cog, append = _logging_cog()
    cog._resolve_audit_actor_detailed = AsyncMock(
        return_value=("8", "Mod", "found", None)
    )
    before = _fake_role(name="Old", permissions=Permissions(send_messages=True))
    after = _fake_role(name="New", permissions=Permissions(manage_channels=True))
    after.guild = before.guild
    await cog.on_guild_role_update(before, after)
    actions = [call.args[1]["action"] for call in append.await_args_list]
    assert actions == ["Role updated"]
    perm_entry = append.await_args_list[0].args[1]
    assert "Manage Channels" in perm_entry["fields"]["Granted"]
    assert "Send Messages" in perm_entry["fields"]["Revoked"]


@pytest.mark.asyncio
async def test_channel_overwrite_only_update_is_logged() -> None:
    cog, append = _logging_cog()
    cog._resolve_audit_actor_detailed = AsyncMock(
        return_value=(None, None, "unavailable", None)
    )
    role = _role_target()
    before = _channel(overwrites={})
    after = _channel(overwrites={role: PermissionOverwrite(view_channel=True)})
    after.guild = SimpleNamespace(id=42)
    await cog.on_guild_channel_update(before, after)
    append.assert_awaited()
    entry = append.await_args.args[1]
    assert entry["event_type"] == "channel_update"
    assert "Overwrite added" in entry["fields"]
    assert entry["fields"]["Actor"] == "Unknown"


@pytest.mark.asyncio
async def test_logging_disabled_skips_permission_event() -> None:
    cog, append = _logging_cog(module_on=False)
    cog._resolve_audit_actor_detailed = AsyncMock(
        return_value=("1", "Mod", "found", None)
    )
    before = _fake_role(name="A", permissions=Permissions.none())
    after = _fake_role(name="A", permissions=Permissions(administrator=True))
    after.guild = before.guild
    await cog.on_guild_role_update(before, after)
    append.assert_not_awaited()


@pytest.mark.asyncio
async def test_audit_actor_found() -> None:
    cog, _append = _logging_cog()
    user = MagicMock()
    user.id = 3
    user.__str__ = lambda self: "Mod"  # type: ignore[method-assign]
    entry = SimpleNamespace(
        action=discord.AuditLogAction.role_update,
        target=SimpleNamespace(id=5),
        created_at=datetime.now(timezone.utc),
        user=user,
    )

    async def _logs(**_kwargs):
        yield entry

    guild = MagicMock()
    guild.id = 1
    guild.audit_logs = MagicMock(side_effect=lambda **kwargs: _logs())
    actor_id, name, status, reason = await cog._resolve_audit_actor_detailed(
        guild,
        discord.AuditLogAction.role_update,
        target_id=5,
        since=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    assert status == "found"
    assert actor_id == "3"
    assert name == "Mod"
    assert reason is None


@pytest.mark.asyncio
async def test_audit_actor_delayed() -> None:
    cog, _append = _logging_cog()
    user = MagicMock()
    user.id = 3
    user.__str__ = lambda self: "Mod"  # type: ignore[method-assign]
    entry = SimpleNamespace(
        action=discord.AuditLogAction.role_update,
        target=SimpleNamespace(id=5),
        created_at=datetime.now(timezone.utc),
        user=user,
    )
    calls = {"n": 0}

    async def _logs(**_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return
            yield  # pragma: no cover — empty async generator
        yield entry

    guild = MagicMock()
    guild.id = 1
    guild.audit_logs = MagicMock(side_effect=lambda **kwargs: _logs())
    with patch("bot.server_logging.asyncio.sleep", new=AsyncMock()):
        actor_id, _name, status, _reason = await cog._resolve_audit_actor_detailed(
            guild,
            discord.AuditLogAction.role_update,
            target_id=5,
            since=datetime.now(timezone.utc) - timedelta(seconds=5),
            max_wait_s=0.6,
        )
    assert status == "delayed"
    assert actor_id == "3"


@pytest.mark.asyncio
async def test_audit_actor_ambiguous() -> None:
    cog, _append = _logging_cog()

    def _entry(user_id: int) -> SimpleNamespace:
        user = MagicMock()
        user.id = user_id
        user.__str__ = lambda self, i=user_id: f"U{i}"  # type: ignore[method-assign]
        return SimpleNamespace(
            action=discord.AuditLogAction.role_update,
            target=SimpleNamespace(id=5),
            created_at=datetime.now(timezone.utc),
            user=user,
        )

    async def _logs(**_kwargs):
        yield _entry(1)
        yield _entry(2)

    guild = MagicMock()
    guild.id = 1
    guild.audit_logs = MagicMock(side_effect=lambda **kwargs: _logs())
    actor_id, _name, status, _reason = await cog._resolve_audit_actor_detailed(
        guild,
        discord.AuditLogAction.role_update,
        target_id=5,
        since=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    assert status == "ambiguous"
    assert actor_id is None


@pytest.mark.asyncio
async def test_audit_actor_unavailable_on_429() -> None:
    cog, _append = _logging_cog()
    error = discord.HTTPException(MagicMock(status=429), "rate limited")
    error.status = 429  # type: ignore[attr-defined]

    async def _logs(**_kwargs):
        raise error
        yield  # pragma: no cover

    guild = MagicMock()
    guild.id = 1
    guild.audit_logs = MagicMock(side_effect=lambda **kwargs: _logs())
    actor_id, _name, status, _reason = await cog._resolve_audit_actor_detailed(
        guild,
        discord.AuditLogAction.role_update,
        target_id=5,
        max_wait_s=0.6,
    )
    assert status == "unavailable"
    assert actor_id is None


@pytest.mark.asyncio
async def test_event_log_key_is_guild_scoped() -> None:
    from bot.server_logging import event_log_key

    assert event_log_key(11) == "norgoth:guild:11:eventlog"
    assert event_log_key(11) != event_log_key(22)
