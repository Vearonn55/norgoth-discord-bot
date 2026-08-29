"""Discord-accurate effective channel permission resolution for REST payloads."""

from __future__ import annotations

from typing import Any, Iterable

from app.security.discord_permissions import (
    ADMINISTRATOR,
    EMBED_LINKS,
    SEND_MESSAGES,
    VIEW_CHANNEL,
    compute_member_permissions,
)

VERIFICATION_CHANNEL_REQUIRED = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS

ORDERED_PERMISSION_LABELS: tuple[tuple[int, str], ...] = (
    (VIEW_CHANNEL, "View Channel"),
    (SEND_MESSAGES, "Send Messages"),
    (EMBED_LINKS, "Embed Links"),
)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def missing_permission_labels(missing_bits: int) -> list[str]:
    """Return human-readable labels for set bits in ``missing_bits``."""

    return [
        label
        for bit, label in ORDERED_PERMISSION_LABELS
        if missing_bits & bit
    ]


def apply_overwrite_chain(
    base: int,
    *,
    guild_id: str,
    member_id: str,
    member_role_ids: Iterable[str],
    roles_by_id: dict[str, dict[str, Any]],
    overwrites: list[dict[str, Any]],
) -> int:
    """Apply one overwrite layer using Discord overwrite order semantics."""

    permissions = base
    everyone_ow = next(
        (ow for ow in overwrites if str(ow.get("id")) == str(guild_id)),
        None,
    )
    if everyone_ow is not None:
        permissions &= ~_as_int(everyone_ow.get("deny"))
        permissions |= _as_int(everyone_ow.get("allow"))

    sorted_role_ids = sorted(
        (
            str(role_id)
            for role_id in member_role_ids
            if str(role_id) != str(guild_id)
        ),
        key=lambda role_id: _as_int(roles_by_id.get(role_id, {}).get("position")),
    )
    for role_id in sorted_role_ids:
        role_ow = next(
            (ow for ow in overwrites if str(ow.get("id")) == role_id),
            None,
        )
        if role_ow is None:
            continue
        permissions &= ~_as_int(role_ow.get("deny"))
        permissions |= _as_int(role_ow.get("allow"))

    member_ow = next(
        (ow for ow in overwrites if str(ow.get("id")) == str(member_id)),
        None,
    )
    if member_ow is not None:
        permissions &= ~_as_int(member_ow.get("deny"))
        permissions |= _as_int(member_ow.get("allow"))
    return permissions


def resolve_effective_channel_permissions(
    *,
    guild_id: str,
    member_user_id: str,
    member_role_ids: Iterable[str],
    roles: Iterable[dict[str, Any]],
    category_overwrites: list[dict[str, Any]] | None = None,
    channel_overwrites: list[dict[str, Any]] | None = None,
) -> tuple[int, bool]:
    """Return effective channel permission bits and whether Administrator bypass applies."""

    roles_by_id: dict[str, dict[str, Any]] = {}
    for role in roles:
        if not isinstance(role, dict):
            continue
        role_id = role.get("id")
        if role_id is None:
            continue
        roles_by_id[str(role_id)] = role

    base = compute_member_permissions(
        guild_id=guild_id,
        owner_id=None,
        member_user_id=member_user_id,
        member_roles=member_role_ids,
        roles=roles,
    )
    if base & ADMINISTRATOR:
        return base, True

    effective = base
    chain_kwargs = {
        "guild_id": guild_id,
        "member_id": member_user_id,
        "member_role_ids": member_role_ids,
        "roles_by_id": roles_by_id,
    }
    if category_overwrites:
        effective = apply_overwrite_chain(
            effective,
            overwrites=category_overwrites,
            **chain_kwargs,
        )
    if channel_overwrites:
        effective = apply_overwrite_chain(
            effective,
            overwrites=channel_overwrites,
            **chain_kwargs,
        )
    return effective, False


def infer_overwrite_scope(
    *,
    base: int,
    effective: int,
    required: int,
    category_overwrites: list[dict[str, Any]] | None,
    channel_overwrites: list[dict[str, Any]] | None,
    guild_id: str,
    member_user_id: str,
    member_role_ids: Iterable[str],
    roles_by_id: dict[str, dict[str, Any]],
) -> str | None:
    """Return ``category``, ``channel``, or ``None`` when guild base bits are the blocker."""

    missing = required & ~effective
    if not missing:
        return None

    chain_kwargs = {
        "guild_id": guild_id,
        "member_id": member_user_id,
        "member_role_ids": member_role_ids,
        "roles_by_id": roles_by_id,
    }
    after_category = base
    if category_overwrites:
        after_category = apply_overwrite_chain(
            base,
            overwrites=category_overwrites,
            **chain_kwargs,
        )
    if required & ~after_category:
        return "category"
    if channel_overwrites:
        return "channel"
    return None


__all__ = [
    "VERIFICATION_CHANNEL_REQUIRED",
    "apply_overwrite_chain",
    "infer_overwrite_scope",
    "missing_permission_labels",
    "resolve_effective_channel_permissions",
]
