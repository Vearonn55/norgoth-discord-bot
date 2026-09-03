"""Command manifest snapshot and permission helper tests."""

from __future__ import annotations

import json
from pathlib import Path

from bot.commands.checks import member_hierarchy_problem, role_hierarchy_problem
from bot.commands.registry import (
    COMMAND_MANIFEST_VERSION,
    COMMANDS,
    command_by_name,
    manifest_snapshot,
)


SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "command_manifest.snapshot.json"
)


REQUIRED_CHAT_COMMANDS = {
    "kick",
    "ban",
    "timeout",
    "purge",
    "userinfo",
    "rank",
    "give-xp",
    "leaderboard",
    "role add",
    "role remove",
    "ticket close",
    "ticket add",
    "ticket remove",
    "invites",
    "invites-top",
    "unsubscribe",
    "help",
    "dashboard",
    "status",
    "avatar",
    "server",
    "roles",
    "unban",
    "untimeout",
    "setnick",
    "vkick",
    "move",
    "lock",
    "unlock",
    "slowmode",
    "level-reset",
    "modlogs",
    "verification pending",
}


def test_manifest_has_unique_names() -> None:
    names = [spec.name for spec in COMMANDS]
    assert len(names) == len(set(names))


def test_manifest_includes_required_commands() -> None:
    present = {spec.name for spec in COMMANDS if spec.command_type == "chat"}
    missing = REQUIRED_CHAT_COMMANDS - present
    assert not missing, f"Missing commands: {sorted(missing)}"


def test_manifest_snapshot_matches() -> None:
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(manifest_snapshot()))
    assert actual == expected
    assert actual["version"] == COMMAND_MANIFEST_VERSION


def test_command_by_name_lookup() -> None:
    assert command_by_name("kick") is not None
    assert command_by_name("KICK") is not None
    assert command_by_name("nope") is None


class _Role:
    def __init__(self, position: int, *, managed: bool = False, name: str = "r") -> None:
        self.position = position
        self.managed = managed
        self.name = name

    def __ge__(self, other: "_Role") -> bool:
        return self.position >= other.position


class _Guild:
    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id


class _Member:
    def __init__(self, member_id: int, guild: _Guild, top: _Role) -> None:
        self.id = member_id
        self.guild = guild
        self.top_role = top


def test_member_hierarchy_blocks_equal_or_higher() -> None:
    guild = _Guild(owner_id=1)
    actor = _Member(2, guild, _Role(5))
    target = _Member(3, guild, _Role(5))
    me = _Member(99, guild, _Role(10))
    assert member_hierarchy_problem(actor, target, me) is not None


def test_member_hierarchy_allows_lower_target() -> None:
    guild = _Guild(owner_id=1)
    actor = _Member(2, guild, _Role(5))
    target = _Member(3, guild, _Role(1))
    me = _Member(99, guild, _Role(10))
    assert member_hierarchy_problem(actor, target, me) is None


def test_role_hierarchy_blocks_managed() -> None:
    guild = _Guild(owner_id=1)
    actor = _Member(2, guild, _Role(5))
    me = _Member(99, guild, _Role(10))
    role = _Role(1, managed=True, name="Bot")
    assert role_hierarchy_problem(actor, role, me) is not None
