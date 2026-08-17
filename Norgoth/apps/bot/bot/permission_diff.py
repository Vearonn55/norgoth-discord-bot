"""Role permission and channel overwrite diffs for Discord server logs.

Uses discord.py permission flag definitions. No network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import discord
from discord import PermissionOverwrite, Permissions

from bot.logging_presentation import FIELD_VALUE_LIMIT

_PREFERRED_FLAG_NAMES = {
    "view_channel",
    "use_external_emojis",
    "manage_roles",
    "manage_expressions",
    "use_external_stickers",
    "create_polls",
}

_STATE_LABEL = {
    "allow": "Allow",
    "deny": "Deny",
    "inherit": "Inherit",
}

_MAX_SECTION_PARTS = 4


def humanize_permission_flag(name: str) -> str:
    """Turn a discord.py flag identifier into a readable English label."""

    return name.replace("_", " ").title()


def unknown_permission_label(mask: int) -> str:
    return f"Unknown permission (0x{mask:x})"


def _canonical_flag_names() -> dict[int, str]:
    """Map each known bit to a single readable flag name (aliases collapsed)."""

    chosen: dict[int, str] = {}
    for name, bit in Permissions.VALID_FLAGS.items():
        existing = chosen.get(bit)
        if existing is None:
            chosen[bit] = name
            continue
        if name in _PREFERRED_FLAG_NAMES:
            chosen[bit] = name
    return chosen


def _known_permission_mask() -> int:
    mask = 0
    for bit in Permissions.VALID_FLAGS.values():
        mask |= bit
    return mask


def _sorted_labels(names: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(names, key=str.casefold))


@dataclass(frozen=True)
class RolePermissionFlagDiff:
    """Granted/revoked discord.py flag identifiers (not localized labels)."""

    granted: tuple[str, ...]
    revoked: tuple[str, ...]
    granted_unknown_mask: int = 0
    revoked_unknown_mask: int = 0

    def is_empty(self) -> bool:
        return (
            not self.granted
            and not self.revoked
            and not self.granted_unknown_mask
            and not self.revoked_unknown_mask
        )


@dataclass(frozen=True)
class RolePermissionDiff:
    granted: tuple[str, ...]
    revoked: tuple[str, ...]

    def is_empty(self) -> bool:
        return not self.granted and not self.revoked


def diff_role_permission_flags(
    before: Permissions,
    after: Permissions,
) -> RolePermissionFlagDiff:
    """Return granted/revoked flag ids. Unchanged bits omitted."""

    before_value = int(before.value)
    after_value = int(after.value)
    granted_bits = after_value & ~before_value
    revoked_bits = before_value & ~after_value
    known = _canonical_flag_names()
    known_mask = _known_permission_mask()

    granted: list[str] = []
    revoked: list[str] = []
    for bit, name in sorted(known.items(), key=lambda item: item[1]):
        if granted_bits & bit:
            granted.append(name)
        if revoked_bits & bit:
            revoked.append(name)

    leftover_granted = granted_bits & ~known_mask
    leftover_revoked = revoked_bits & ~known_mask
    return RolePermissionFlagDiff(
        granted=_sorted_labels(granted),
        revoked=_sorted_labels(revoked),
        granted_unknown_mask=leftover_granted,
        revoked_unknown_mask=leftover_revoked,
    )


def diff_role_permissions(
    before: Permissions,
    after: Permissions,
) -> RolePermissionDiff:
    """Return granted/revoked English labels for Discord embeds."""

    flags = diff_role_permission_flags(before, after)
    granted = [humanize_permission_flag(name) for name in flags.granted]
    revoked = [humanize_permission_flag(name) for name in flags.revoked]
    if flags.granted_unknown_mask:
        granted.append(unknown_permission_label(flags.granted_unknown_mask))
    if flags.revoked_unknown_mask:
        revoked.append(unknown_permission_label(flags.revoked_unknown_mask))
    return RolePermissionDiff(
        granted=_sorted_labels(granted),
        revoked=_sorted_labels(revoked),
    )


def _tri_state(overwrite: PermissionOverwrite | None, flag: str) -> str:
    if overwrite is None:
        return "inherit"
    value = getattr(overwrite, flag, None)
    if value is True:
        return "allow"
    if value is False:
        return "deny"
    return "inherit"


def _target_identity(target: Any) -> tuple[str, int, str]:
    tid = int(getattr(target, "id", 0) or 0)
    if isinstance(target, discord.Role):
        name = str(getattr(target, "name", "") or tid)
        return "role", tid, f"@{name}"
    if isinstance(target, (discord.Member, discord.User)):
        return "member", tid, str(target)
    type_hint = getattr(target, "type", None)
    if type_hint is discord.Role or getattr(type_hint, "__name__", "") == "Role":
        name = str(getattr(target, "name", "") or tid)
        return "role", tid, f"@{name}"
    display = getattr(target, "name", None) or getattr(target, "display_name", None)
    label = str(display) if display else f"Member {tid}"
    return "member", tid, label


def _format_target(kind: str, label: str, target_id: int) -> str:
    kind_tag = "role" if kind == "role" else "member"
    return f"{label} ({kind_tag} {target_id})"


def _explicit_overwrite_summary(overwrite: PermissionOverwrite) -> str:
    allows: list[str] = []
    denies: list[str] = []
    for name in sorted(_canonical_flag_names().values()):
        state = _tri_state(overwrite, name)
        label = humanize_permission_flag(name)
        if state == "allow":
            allows.append(label)
        elif state == "deny":
            denies.append(label)
    parts: list[str] = []
    if allows:
        parts.append("Allow " + ", ".join(allows))
    if denies:
        parts.append("Deny " + ", ".join(denies))
    return "; ".join(parts) if parts else "(empty)"


def _overwrite_map(
    overwrites: Mapping[Any, PermissionOverwrite] | None,
) -> dict[tuple[str, int], tuple[str, PermissionOverwrite]]:
    mapped: dict[tuple[str, int], tuple[str, PermissionOverwrite]] = {}
    for target, overwrite in dict(overwrites or {}).items():
        kind, tid, label = _target_identity(target)
        mapped[(kind, tid)] = (label, overwrite)
    return mapped


def _transition_bucket(before_state: str, after_state: str) -> str | None:
    if before_state == after_state:
        return None
    if after_state == "allow":
        return "granted"
    if after_state == "deny":
        return "denied"
    return "inherited"


@dataclass(frozen=True)
class OverwriteChange:
    """One Allow/Deny/Inherit transition or overwrite add/remove for a flag."""

    target_kind: str
    target_id: str
    target_name: str
    permission: str
    previous: str
    next: str
    change: str
    unknown_mask: str | None = None


@dataclass
class ChannelOverwriteDiff:
    granted: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    inherited: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    category_synced: bool = False

    def is_empty(self) -> bool:
        return not (
            self.granted
            or self.denied
            or self.inherited
            or self.added
            or self.removed
            or self.category_synced
        )

    def change_count(self) -> int:
        return (
            len(self.granted)
            + len(self.denied)
            + len(self.inherited)
            + len(self.added)
            + len(self.removed)
        )


def detect_category_sync(before: Any, after: Any) -> bool:
    """True when Discord synchronized the channel with its parent category."""

    synced_after = getattr(after, "permissions_synced", None)
    synced_before = getattr(before, "permissions_synced", None)
    if synced_after is True and synced_before is not True:
        return True
    category = getattr(after, "category", None)
    if category is None:
        return False
    after_states = {
        key: overwrite
        for key, (_label, overwrite) in _overwrite_map(
            getattr(after, "overwrites", None)
        ).items()
    }
    category_states = {
        key: overwrite
        for key, (_label, overwrite) in _overwrite_map(
            getattr(category, "overwrites", None)
        ).items()
    }
    before_states = {
        key: overwrite
        for key, (_label, overwrite) in _overwrite_map(
            getattr(before, "overwrites", None)
        ).items()
    }
    return after_states == category_states and after_states != before_states


def _explicit_flag_states(overwrite: PermissionOverwrite) -> list[tuple[str, str]]:
    states: list[tuple[str, str]] = []
    for name in sorted(_canonical_flag_names().values()):
        state = _tri_state(overwrite, name)
        if state != "inherit":
            states.append((name, state))
    return states


def diff_channel_overwrite_items(before: Any, after: Any) -> list[OverwriteChange]:
    """Structured Allow/Deny/Inherit transitions. Unchanged flags omitted."""

    items: list[OverwriteChange] = []
    before_map = _overwrite_map(getattr(before, "overwrites", None))
    after_map = _overwrite_map(getattr(after, "overwrites", None))
    flag_names = sorted(_canonical_flag_names().values())

    for key in sorted(set(before_map) | set(after_map)):
        kind, tid = key
        before_entry = before_map.get(key)
        after_entry = after_map.get(key)
        target_id = str(tid)
        if before_entry is None and after_entry is not None:
            label, overwrite = after_entry
            explicit = _explicit_flag_states(overwrite)
            if not explicit:
                continue
            for name, state in explicit:
                items.append(
                    OverwriteChange(
                        target_kind=kind,
                        target_id=target_id,
                        target_name=label,
                        permission=name,
                        previous="inherit",
                        next=state,
                        change="overwrite_added",
                    )
                )
            continue
        if before_entry is not None and after_entry is None:
            label, overwrite = before_entry
            explicit = _explicit_flag_states(overwrite)
            if not explicit:
                continue
            for name, state in explicit:
                items.append(
                    OverwriteChange(
                        target_kind=kind,
                        target_id=target_id,
                        target_name=label,
                        permission=name,
                        previous=state,
                        next="inherit",
                        change="overwrite_removed",
                    )
                )
            continue
        if before_entry is None or after_entry is None:
            continue
        before_label, before_ow = before_entry
        _after_label, after_ow = after_entry
        for name in flag_names:
            previous = _tri_state(before_ow, name)
            current = _tri_state(after_ow, name)
            if previous == current:
                continue
            items.append(
                OverwriteChange(
                    target_kind=kind,
                    target_id=target_id,
                    target_name=before_label,
                    permission=name,
                    previous=previous,
                    next=current,
                    change="transition",
                )
            )
    return items


def diff_channel_overwrites(before: Any, after: Any) -> ChannelOverwriteDiff:
    """Diff Allow/Deny/Inherit overwrite maps on two guild channel snapshots."""

    result = ChannelOverwriteDiff(category_synced=detect_category_sync(before, after))
    before_map = _overwrite_map(getattr(before, "overwrites", None))
    after_map = _overwrite_map(getattr(after, "overwrites", None))

    for item in diff_channel_overwrite_items(before, after):
        tid = int(item.target_id)
        target = _format_target(item.target_kind, item.target_name, tid)
        perm = humanize_permission_flag(item.permission)
        if item.change == "overwrite_added":
            key = (item.target_kind, tid)
            after_entry = after_map.get(key)
            if after_entry is not None and not any(
                line.startswith(f"{target}:") for line in result.added
            ):
                _label, overwrite = after_entry
                result.added.append(
                    f"{target}: {_explicit_overwrite_summary(overwrite)}"
                )
            continue
        if item.change == "overwrite_removed":
            key = (item.target_kind, tid)
            before_entry = before_map.get(key)
            if before_entry is not None and not any(
                line.startswith(f"{target}:") for line in result.removed
            ):
                _label, overwrite = before_entry
                result.removed.append(
                    f"{target}: {_explicit_overwrite_summary(overwrite)}"
                )
            continue
        bucket = _transition_bucket(item.previous, item.next)
        if bucket is None:
            continue
        line = (
            f"{target}: {perm} "
            f"({_STATE_LABEL[item.previous]} → {_STATE_LABEL[item.next]})"
        )
        getattr(result, bucket).append(line)

    return result


def pack_section_lines(
    name: str,
    lines: list[str] | tuple[str, ...],
    *,
    joiner: str = "\n",
    max_parts: int = _MAX_SECTION_PARTS,
) -> dict[str, str]:
    """Fit lines into Discord field values; split or summarize rather than drop all."""

    values = [str(line) for line in lines if str(line).strip()]
    if not values:
        return {}

    parts: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    remaining = list(values)

    def _fits(existing: list[str], existing_len: int, piece: str) -> bool:
        extra = len(piece) + (len(joiner) if existing else 0)
        return existing_len + extra <= FIELD_VALUE_LIMIT

    while remaining:
        piece = remaining[0]
        if len(piece) > FIELD_VALUE_LIMIT:
            piece = piece[: FIELD_VALUE_LIMIT - 1] + "…"
        if current and not _fits(current, current_len, piece):
            parts.append(current)
            current = []
            current_len = 0
            if len(parts) >= max_parts:
                break
            continue
        remaining.pop(0)
        extra = len(piece) + (len(joiner) if current else 0)
        current.append(piece)
        current_len += extra

    omitted = len(remaining)
    if current:
        if len(parts) >= max_parts:
            omitted += len(current)
        else:
            parts.append(current)

    if omitted:
        suffix = f"…and {omitted} more"
        if not parts:
            parts.append([suffix])
        else:
            last = parts[-1]
            joined = joiner.join(last)
            while last and len(joined) + len(joiner) + len(suffix) > FIELD_VALUE_LIMIT:
                last.pop()
                omitted += 1
                suffix = f"…and {omitted} more"
                joined = joiner.join(last)
            last.append(suffix)

    if len(parts) == 1:
        return {name: joiner.join(parts[0])}
    packed: dict[str, str] = {}
    for index, part in enumerate(parts, start=1):
        packed[f"{name} ({index})"] = joiner.join(part)
    return packed


def role_permission_fields(diff: RolePermissionDiff) -> dict[str, str]:
    fields: dict[str, str] = {}
    fields.update(pack_section_lines("Granted", diff.granted, joiner=", "))
    fields.update(pack_section_lines("Revoked", diff.revoked, joiner=", "))
    return fields


def channel_overwrite_fields(diff: ChannelOverwriteDiff) -> dict[str, str]:
    fields: dict[str, str] = {}
    fields.update(pack_section_lines("Granted", diff.granted))
    fields.update(pack_section_lines("Denied", diff.denied))
    fields.update(pack_section_lines("Inherited/Reset", diff.inherited))
    fields.update(pack_section_lines("Overwrite added", diff.added))
    fields.update(pack_section_lines("Overwrite removed", diff.removed))
    if diff.category_synced:
        fields["Sync"] = "permissions synchronized with category"
    return fields
