"""Versioned field-level audit diffs captured at Discord event time.

Stores only the normalized diff. No network I/O. Does not reconstruct state
from live Discord resources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from discord import Permissions

from bot.permission_diff import (
    OverwriteChange,
    RolePermissionFlagDiff,
    diff_channel_overwrite_items,
    diff_role_permission_flags,
)

SCHEMA_VERSION = 1
SOURCE_DISCORD_GATEWAY = "discord_gateway"

MAX_FIELD_CHANGES = 32
MAX_PERM_CHANGES = 200
TOPIC_MAX = 512
NAME_MAX = 128
REASON_MAX = 512
PAYLOAD_MAX_BYTES = 32_768

CHANNEL_ATTR_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "name"),
    ("topic", "topic"),
    ("nsfw", "nsfw"),
    ("slowmode_delay", "slowmode_delay"),
    ("position", "position"),
    ("type", "type"),
    ("bitrate", "bitrate"),
    ("user_limit", "user_limit"),
)

THREAD_ATTR_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "name"),
    ("archived", "archived"),
    ("locked", "locked"),
    ("auto_archive_duration", "auto_archive_duration"),
)

ROLE_ATTR_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "name"),
    ("hoist", "hoist"),
    ("mentionable", "mentionable"),
    ("unicode_emoji", "unicode_emoji"),
    ("position", "position"),
)

_MOCK_TYPE_NAMES = {"MagicMock", "AsyncMock", "Mock"}
_MISSING = object()


@dataclass
class FieldChange:
    field: str
    previous: Any
    next: Any


@dataclass
class AuditDetail:
    event_type: str
    target: dict[str, Any]
    actor: dict[str, Any] | None = None
    source: str = SOURCE_DISCORD_GATEWAY
    reason: str | None = None
    correlation_id: str | None = None
    field_changes: list[FieldChange] = field(default_factory=list)
    permission_changes: dict[str, Any] | None = None
    truncated: bool = False

    def is_empty(self) -> bool:
        perms = self.permission_changes
        perm_empty = True
        if isinstance(perms, dict):
            if perms.get("kind") == "role_bits":
                perm_empty = not perms.get("granted") and not perms.get("revoked")
            elif perms.get("kind") == "overwrites":
                perm_empty = not perms.get("items")
        return not self.field_changes and perm_empty

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "event_type": self.event_type,
            "target": self.target,
            "actor": self.actor,
            "source": self.source,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "field_changes": [
                {
                    "field": change.field,
                    "previous": change.previous,
                    "next": change.next,
                }
                for change in self.field_changes
            ],
            "permission_changes": self.permission_changes,
            "truncated": self.truncated,
        }
        return payload


def _is_mock(value: Any) -> bool:
    return type(value).__name__ in _MOCK_TYPE_NAMES


def _raw_attr(obj: Any, name: str) -> Any:
    if obj is None or not hasattr(obj, name):
        return _MISSING
    value = getattr(obj, name)
    if _is_mock(value):
        return _MISSING
    return value


def _normalize_text(value: Any, *, limit: int = NAME_MAX) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _normalize_scalar(field_name: str, value: Any) -> Any:
    if field_name in {"name", "unicode_emoji"}:
        return _normalize_text(value, limit=NAME_MAX)
    if field_name == "topic":
        return _normalize_text(value, limit=TOPIC_MAX)
    if field_name == "type":
        if value is None:
            return None
        return str(value)
    if field_name == "display_icon":
        if value is None:
            return None
        return str(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _values_equal(previous: Any, current: Any) -> bool:
    if previous == current:
        return True
    if previous in ("", None) and current in ("", None):
        return True
    return False


def _diff_attr_fields(
    before: Any,
    after: Any,
    pairs: tuple[tuple[str, str], ...],
) -> list[FieldChange]:
    changes: list[FieldChange] = []
    for field_name, attr in pairs:
        left = _raw_attr(before, attr)
        right = _raw_attr(after, attr)
        if left is _MISSING or right is _MISSING:
            continue
        previous = _normalize_scalar(field_name, left)
        current = _normalize_scalar(field_name, right)
        if _values_equal(previous, current):
            continue
        changes.append(FieldChange(field=field_name, previous=previous, next=current))
    return changes


def _parent_identity(channel: Any) -> dict[str, str] | None:
    parent_id = _raw_attr(channel, "parent_id")
    if parent_id is _MISSING or parent_id is None:
        return None
    parent = _raw_attr(channel, "category")
    name = ""
    if parent is not _MISSING and parent is not None:
        raw_name = _raw_attr(parent, "name")
        if raw_name is not _MISSING:
            name = _normalize_text(raw_name)
    return {"id": str(parent_id), "name": name}


def diff_channel_fields(before: Any, after: Any) -> list[FieldChange]:
    changes = _diff_attr_fields(before, after, CHANNEL_ATTR_FIELDS)
    before_parent_id = _raw_attr(before, "parent_id")
    after_parent_id = _raw_attr(after, "parent_id")
    if before_parent_id is not _MISSING and after_parent_id is not _MISSING:
        left = None if before_parent_id is None else str(before_parent_id)
        right = None if after_parent_id is None else str(after_parent_id)
        if left != right:
            changes.append(
                FieldChange(
                    field="parent",
                    previous=_parent_identity(before),
                    next=_parent_identity(after),
                )
            )
    return changes


def diff_thread_fields(before: Any, after: Any) -> list[FieldChange]:
    return _diff_attr_fields(before, after, THREAD_ATTR_FIELDS)


def diff_role_fields(before: Any, after: Any) -> list[FieldChange]:
    changes = _diff_attr_fields(before, after, ROLE_ATTR_FIELDS)
    before_color = _role_color(before)
    after_color = _role_color(after)
    if before_color is not _MISSING and after_color is not _MISSING:
        if before_color != after_color:
            changes.append(
                FieldChange(field="color", previous=before_color, next=after_color)
            )
    before_icon = _role_icon(before)
    after_icon = _role_icon(after)
    if before_icon is not _MISSING and after_icon is not _MISSING:
        if not _values_equal(before_icon, after_icon):
            changes.append(
                FieldChange(field="icon", previous=before_icon, next=after_icon)
            )
    return changes


def _role_color(role: Any) -> Any:
    colour = _raw_attr(role, "colour")
    if colour is _MISSING:
        colour = _raw_attr(role, "color")
    if colour is _MISSING:
        return _MISSING
    if colour is None:
        return 0
    value = _raw_attr(colour, "value")
    if value is _MISSING:
        if isinstance(colour, int):
            return int(colour)
        return _MISSING
    try:
        return int(value)
    except (TypeError, ValueError):
        return _MISSING


def _role_icon(role: Any) -> Any:
    icon = _raw_attr(role, "display_icon")
    if icon is _MISSING:
        icon = _raw_attr(role, "icon")
    if icon is _MISSING:
        return _MISSING
    if icon is None:
        return None
    return str(icon)


def _role_permission_payload(diff: RolePermissionFlagDiff) -> dict[str, Any] | None:
    if diff.is_empty():
        return None
    granted: list[dict[str, str]] = [
        {"permission": name} for name in diff.granted
    ]
    revoked: list[dict[str, str]] = [
        {"permission": name} for name in diff.revoked
    ]
    if diff.granted_unknown_mask:
        granted.append(
            {
                "permission": "unknown",
                "unknown_mask": f"0x{diff.granted_unknown_mask:x}",
            }
        )
    if diff.revoked_unknown_mask:
        revoked.append(
            {
                "permission": "unknown",
                "unknown_mask": f"0x{diff.revoked_unknown_mask:x}",
            }
        )
    return {"kind": "role_bits", "granted": granted, "revoked": revoked}


def _overwrite_payload(
    items: list[OverwriteChange],
    *,
    category_synced: bool = False,
) -> dict[str, Any] | None:
    if not items and not category_synced:
        return None
    serialized = [
        {
            "target_kind": item.target_kind,
            "target_id": item.target_id,
            "target_name": item.target_name,
            "permission": item.permission,
            "previous": item.previous,
            "next": item.next,
            "change": item.change,
            "unknown_mask": item.unknown_mask,
        }
        for item in items
    ]
    return {
        "kind": "overwrites",
        "items": serialized,
        "category_synced": category_synced,
    }


def _clip_detail(detail: AuditDetail) -> AuditDetail:
    if len(detail.field_changes) > MAX_FIELD_CHANGES:
        detail.field_changes = detail.field_changes[:MAX_FIELD_CHANGES]
        detail.truncated = True
    perms = detail.permission_changes
    if isinstance(perms, dict) and perms.get("kind") == "overwrites":
        items = perms.get("items") or []
        if len(items) > MAX_PERM_CHANGES:
            perms = dict(perms)
            perms["items"] = items[:MAX_PERM_CHANGES]
            detail.permission_changes = perms
            detail.truncated = True
    if isinstance(perms, dict) and perms.get("kind") == "role_bits":
        granted = list(perms.get("granted") or [])
        revoked = list(perms.get("revoked") or [])
        if len(granted) + len(revoked) > MAX_PERM_CHANGES:
            keep_granted = granted[: min(len(granted), MAX_PERM_CHANGES)]
            remaining = MAX_PERM_CHANGES - len(keep_granted)
            perms = dict(perms)
            perms["granted"] = keep_granted
            perms["revoked"] = revoked[:remaining]
            detail.permission_changes = perms
            detail.truncated = True
    return detail


def _actor_payload(
    actor_id: str | None,
    actor_name: str | None,
) -> dict[str, Any] | None:
    if not actor_id and not actor_name:
        return None
    payload: dict[str, Any] = {}
    if actor_id:
        payload["id"] = str(actor_id)
    if actor_name:
        payload["name"] = _normalize_text(actor_name)
    return payload or None


def _reason_value(reason: str | None) -> str | None:
    if not reason:
        return None
    text = str(reason).strip()
    if not text:
        return None
    return text[:REASON_MAX]


def target_from_channel(channel: Any, *, kind: str = "channel") -> dict[str, Any]:
    channel_id = _raw_attr(channel, "id")
    name = _raw_attr(channel, "name")
    channel_type = _raw_attr(channel, "type")
    payload: dict[str, Any] = {"kind": kind}
    if channel_id is not _MISSING:
        payload["id"] = str(channel_id)
    if name is not _MISSING:
        payload["name"] = _normalize_text(name)
    if channel_type is not _MISSING and channel_type is not None:
        payload["type"] = str(channel_type)
    return payload


def target_from_role(role: Any) -> dict[str, Any]:
    role_id = _raw_attr(role, "id")
    name = _raw_attr(role, "name")
    payload: dict[str, Any] = {"kind": "role"}
    if role_id is not _MISSING:
        payload["id"] = str(role_id)
    if name is not _MISSING:
        payload["name"] = _normalize_text(name)
    return payload


def build_channel_update_detail(
    before: Any,
    after: Any,
    *,
    actor_id: str | None = None,
    actor_name: str | None = None,
    reason: str | None = None,
    category_synced: bool = False,
) -> AuditDetail:
    overwrite_items = diff_channel_overwrite_items(before, after)
    detail = AuditDetail(
        event_type="channel_update",
        target=target_from_channel(after, kind="channel"),
        actor=_actor_payload(actor_id, actor_name),
        reason=_reason_value(reason),
        field_changes=diff_channel_fields(before, after),
        permission_changes=_overwrite_payload(
            overwrite_items, category_synced=category_synced
        ),
    )
    return _clip_detail(detail)


def build_thread_update_detail(
    before: Any,
    after: Any,
    *,
    actor_id: str | None = None,
    actor_name: str | None = None,
    reason: str | None = None,
) -> AuditDetail:
    detail = AuditDetail(
        event_type="thread_update",
        target=target_from_channel(after, kind="thread"),
        actor=_actor_payload(actor_id, actor_name),
        reason=_reason_value(reason),
        field_changes=diff_thread_fields(before, after),
    )
    return _clip_detail(detail)


_EMBED_FIELD_LABELS = {
    "name": "Name",
    "topic": "Topic",
    "nsfw": "NSFW",
    "slowmode_delay": "Slowmode",
    "parent": "Category",
    "position": "Position",
    "type": "Type",
    "bitrate": "Bitrate",
    "user_limit": "User limit",
    "archived": "Archived",
    "locked": "Locked",
    "auto_archive_duration": "Auto-archive",
    "color": "Color",
    "hoist": "Hoist",
    "mentionable": "Mentionable",
    "icon": "Icon",
    "unicode_emoji": "Emoji",
}


def _embed_value(value: Any) -> str:
    if value is None:
        return "(empty)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        name = value.get("name") or value.get("id") or ""
        return str(name) if name else "(none)"
    text = str(value)
    if not text:
        return "(empty)"
    if len(text) > 200:
        return text[:199] + "…"
    return text


def discord_embed_field_changes(changes: list[FieldChange]) -> dict[str, str]:
    """English previous → next lines for Discord log embeds."""

    fields: dict[str, str] = {}
    for change in changes:
        label = _EMBED_FIELD_LABELS.get(change.field, change.field)
        fields[label] = f"{_embed_value(change.previous)} → {_embed_value(change.next)}"
    return fields


def build_role_update_detail(
    before: Any,
    after: Any,
    *,
    actor_id: str | None = None,
    actor_name: str | None = None,
    reason: str | None = None,
) -> AuditDetail:
    perm_diff = RolePermissionFlagDiff(granted=(), revoked=())
    before_perms = _raw_attr(before, "permissions")
    after_perms = _raw_attr(after, "permissions")
    if (
        before_perms is not _MISSING
        and after_perms is not _MISSING
        and isinstance(before_perms, Permissions)
        and isinstance(after_perms, Permissions)
    ):
        perm_diff = diff_role_permission_flags(before_perms, after_perms)
    detail = AuditDetail(
        event_type="role_update",
        target=target_from_role(after),
        actor=_actor_payload(actor_id, actor_name),
        reason=_reason_value(reason),
        field_changes=diff_role_fields(before, after),
        permission_changes=_role_permission_payload(perm_diff),
    )
    return _clip_detail(detail)
