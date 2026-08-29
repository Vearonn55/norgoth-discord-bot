"""Tests for Discord effective channel permission resolution."""

from __future__ import annotations

from app.security.discord_effective_permissions import (
    VERIFICATION_CHANNEL_REQUIRED,
    apply_overwrite_chain,
    infer_overwrite_scope,
    missing_permission_labels,
    resolve_effective_channel_permissions,
)
from app.security.discord_permissions import (
    ADMINISTRATOR,
    EMBED_LINKS,
    SEND_MESSAGES,
    VIEW_CHANNEL,
)


def _roles(*entries: tuple[str, int, int]) -> list[dict[str, object]]:
    return [
        {"id": role_id, "permissions": str(permissions), "position": position}
        for role_id, permissions, position in entries
    ]


def test_all_required_permissions_present() -> None:
    guild_id = "1"
    effective, admin_bypass = resolve_effective_channel_permissions(
        guild_id=guild_id,
        member_user_id="bot",
        member_role_ids=["bot-role"],
        roles=_roles(
            (guild_id, VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS, 0),
            ("bot-role", 0, 5),
        ),
        channel_overwrites=[],
    )
    assert admin_bypass is False
    assert effective & VERIFICATION_CHANNEL_REQUIRED == VERIFICATION_CHANNEL_REQUIRED


def test_missing_permission_labels_subset() -> None:
    labels = missing_permission_labels(SEND_MESSAGES | EMBED_LINKS)
    assert labels == ["Send Messages", "Embed Links"]


def test_administrator_bypass() -> None:
    guild_id = "1"
    _, admin_bypass = resolve_effective_channel_permissions(
        guild_id=guild_id,
        member_user_id="bot",
        member_role_ids=["bot-role"],
        roles=_roles((guild_id, 0, 0), ("bot-role", ADMINISTRATOR, 5)),
        category_overwrites=[
            {"id": guild_id, "allow": "0", "deny": str(VIEW_CHANNEL)},
        ],
        channel_overwrites=[
            {"id": guild_id, "allow": "0", "deny": str(SEND_MESSAGES)},
        ],
    )
    assert admin_bypass is True


def test_category_overwrites_apply_before_channel() -> None:
    guild_id = "1"
    effective, _ = resolve_effective_channel_permissions(
        guild_id=guild_id,
        member_user_id="bot",
        member_role_ids=["bot-role"],
        roles=_roles(
            (guild_id, VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS, 0),
            ("bot-role", 0, 5),
        ),
        category_overwrites=[
            {"id": guild_id, "allow": "0", "deny": str(VIEW_CHANNEL)},
        ],
        channel_overwrites=[
            {"id": "bot-role", "allow": str(VIEW_CHANNEL), "deny": "0"},
        ],
    )
    assert effective & VIEW_CHANNEL
    assert effective & VERIFICATION_CHANNEL_REQUIRED == VERIFICATION_CHANNEL_REQUIRED


def test_conflicting_role_overwrites_use_sequential_order() -> None:
    guild_id = "1"
    base = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS
    roles_by_id = {
        guild_id: {"id": guild_id, "position": 0},
        "low-role": {"id": "low-role", "position": 1},
        "high-role": {"id": "high-role", "position": 5},
    }
    overwrites = [
        {"id": "low-role", "allow": str(SEND_MESSAGES), "deny": "0"},
        {"id": "high-role", "allow": "0", "deny": str(SEND_MESSAGES)},
    ]

    sequential = apply_overwrite_chain(
        base,
        guild_id=guild_id,
        member_id="bot",
        member_role_ids=["low-role", "high-role"],
        roles_by_id=roles_by_id,
        overwrites=overwrites,
    )
    aggregated_allow = SEND_MESSAGES
    aggregated_deny = SEND_MESSAGES
    or_buggy = base & ~aggregated_deny | aggregated_allow

    assert sequential & SEND_MESSAGES == 0
    assert or_buggy & SEND_MESSAGES


def test_member_overwrite_applies_last() -> None:
    guild_id = "1"
    base = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS
    roles_by_id = {guild_id: {"id": guild_id, "position": 0}}
    effective = apply_overwrite_chain(
        base,
        guild_id=guild_id,
        member_id="bot",
        member_role_ids=[],
        roles_by_id=roles_by_id,
        overwrites=[
            {"id": guild_id, "allow": "0", "deny": str(VIEW_CHANNEL)},
            {"id": "bot", "allow": str(VIEW_CHANNEL), "deny": "0"},
        ],
    )
    assert effective & VIEW_CHANNEL


def test_infer_overwrite_scope_category() -> None:
    guild_id = "1"
    base = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS
    roles_by_id = {guild_id: {"id": guild_id, "position": 0}}
    category_overwrites = [
        {"id": guild_id, "allow": "0", "deny": str(SEND_MESSAGES)},
    ]
    effective = apply_overwrite_chain(
        base,
        guild_id=guild_id,
        member_id="bot",
        member_role_ids=[],
        roles_by_id=roles_by_id,
        overwrites=category_overwrites,
    )
    scope = infer_overwrite_scope(
        base=base,
        effective=effective,
        required=VERIFICATION_CHANNEL_REQUIRED,
        category_overwrites=category_overwrites,
        channel_overwrites=[],
        guild_id=guild_id,
        member_user_id="bot",
        member_role_ids=[],
        roles_by_id=roles_by_id,
    )
    assert scope == "category"


def test_large_bitfield_precision() -> None:
    guild_id = "1"
    large_allow = 1 << 40
    effective = apply_overwrite_chain(
        0,
        guild_id=guild_id,
        member_id="bot",
        member_role_ids=[],
        roles_by_id={guild_id: {"id": guild_id, "position": 0}},
        overwrites=[{"id": guild_id, "allow": str(large_allow), "deny": "0"}],
    )
    assert effective == large_allow
