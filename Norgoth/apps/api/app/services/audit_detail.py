"""Sanitize and bound versioned audit-event payloads for Postgres ingest."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = 1
EVENT_LOG_CAP = 1000
MODERATION_LOG_CAP = 500
PAYLOAD_MAX_BYTES = 32_768
MAX_FIELD_CHANGES = 32
MAX_PERM_CHANGES = 200
TOPIC_MAX = 512
REASON_MAX = 512
NAME_MAX = 128

FIELD_ALLOWLIST = {
    "name",
    "topic",
    "nsfw",
    "slowmode_delay",
    "parent",
    "position",
    "type",
    "bitrate",
    "user_limit",
    "archived",
    "locked",
    "auto_archive_duration",
    "color",
    "hoist",
    "mentionable",
    "icon",
    "unicode_emoji",
}

PERM_STATES = {"allow", "deny", "inherit"}
PERM_CHANGE_KINDS = {"transition", "overwrite_added", "overwrite_removed"}
TARGET_KINDS = {"channel", "thread", "role", "member"}

_SNOWFLAKE_RE = re.compile(r"^[0-9]{5,25}$")
_SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|authorization|cookie|webhook|password|api[_-]?key|"
    r"session|exception|traceback|stack|ip_address|\bip\b)",
    re.IGNORECASE,
)


def is_snowflake(value: str | None) -> bool:
    return bool(value and _SNOWFLAKE_RE.fullmatch(value))


def _clip_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY_RE.search(str(key)):
                continue
            cleaned[str(key)] = _redact_mapping(item)
        return cleaned
    if isinstance(value, list):
        return [_redact_mapping(item) for item in value[:200]]
    if isinstance(value, str):
        return value[:2048]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:256]


def _sanitize_field_change(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    field_name = str(raw.get("field") or "")
    if field_name not in FIELD_ALLOWLIST:
        return None
    previous = _redact_mapping(raw.get("previous"))
    current = _redact_mapping(raw.get("next"))
    if field_name in {"name", "topic", "unicode_emoji"}:
        limit = TOPIC_MAX if field_name == "topic" else NAME_MAX
        if isinstance(previous, str):
            previous = previous[:limit]
        if isinstance(current, str):
            current = current[:limit]
    return {"field": field_name, "previous": previous, "next": current}


def _sanitize_perm_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    permission = str(raw.get("permission") or "")
    if not permission:
        return None
    previous = str(raw.get("previous") or "inherit")
    nxt = str(raw.get("next") or "inherit")
    change = str(raw.get("change") or "transition")
    if previous not in PERM_STATES:
        previous = "inherit"
    if nxt not in PERM_STATES:
        nxt = "inherit"
    if change not in PERM_CHANGE_KINDS:
        change = "transition"
    target_kind = str(raw.get("target_kind") or "role")
    if target_kind not in {"role", "member"}:
        target_kind = "role"
    item: dict[str, Any] = {
        "target_kind": target_kind,
        "target_id": str(raw.get("target_id") or "")[:32],
        "target_name": _clip_text(raw.get("target_name"), NAME_MAX) or "",
        "permission": permission[:64],
        "previous": previous,
        "next": nxt,
        "change": change,
        "unknown_mask": _clip_text(raw.get("unknown_mask"), 24),
    }
    return item


def _sanitize_role_bit(raw: Any) -> dict[str, str] | None:
    if isinstance(raw, str):
        return {"permission": raw[:64]}
    if not isinstance(raw, dict):
        return None
    permission = str(raw.get("permission") or "")[:64]
    if not permission:
        return None
    item: dict[str, str] = {"permission": permission}
    mask = raw.get("unknown_mask")
    if mask:
        item["unknown_mask"] = str(mask)[:24]
    return item


def sanitize_permission_changes(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    if kind == "role_bits":
        granted = [
            item
            for item in (_sanitize_role_bit(value) for value in (raw.get("granted") or []))
            if item
        ][:MAX_PERM_CHANGES]
        revoked = [
            item
            for item in (_sanitize_role_bit(value) for value in (raw.get("revoked") or []))
            if item
        ]
        remaining = max(0, MAX_PERM_CHANGES - len(granted))
        revoked = revoked[:remaining]
        return {"kind": "role_bits", "granted": granted, "revoked": revoked}
    if kind == "overwrites":
        items = [
            item
            for item in (_sanitize_perm_item(value) for value in (raw.get("items") or []))
            if item
        ][:MAX_PERM_CHANGES]
        return {
            "kind": "overwrites",
            "items": items,
            "category_synced": bool(raw.get("category_synced")),
        }
    return None


def sanitize_detail(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    schema_version = raw.get("schema_version")
    try:
        version = int(schema_version)
    except (TypeError, ValueError):
        version = 0
    if version != SCHEMA_VERSION:
        return None

    target_raw = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    target_kind = str(target_raw.get("kind") or "channel")
    if target_kind not in TARGET_KINDS:
        target_kind = "channel"
    target = {
        "kind": target_kind,
        "id": str(target_raw.get("id") or "")[:32],
        "name": _clip_text(target_raw.get("name"), NAME_MAX) or "",
    }
    if target_raw.get("type") is not None:
        target["type"] = str(target_raw.get("type"))[:32]

    actor = None
    actor_raw = raw.get("actor")
    if isinstance(actor_raw, dict):
        actor = {
            "id": str(actor_raw.get("id") or "")[:32] or None,
            "name": _clip_text(actor_raw.get("name"), NAME_MAX),
        }

    field_changes = [
        item
        for item in (_sanitize_field_change(value) for value in (raw.get("field_changes") or []))
        if item
    ]
    truncated = bool(raw.get("truncated"))
    if len(field_changes) > MAX_FIELD_CHANGES:
        field_changes = field_changes[:MAX_FIELD_CHANGES]
        truncated = True

    permission_changes = sanitize_permission_changes(raw.get("permission_changes"))
    if (
        isinstance(permission_changes, dict)
        and permission_changes.get("kind") == "overwrites"
        and len(permission_changes.get("items") or []) > MAX_PERM_CHANGES
    ):
        truncated = True

    source = str(raw.get("source") or "discord_gateway")[:32]
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": str(raw.get("event_type") or "")[:64],
        "target": target,
        "actor": actor,
        "source": source,
        "reason": _clip_text(raw.get("reason"), REASON_MAX),
        "correlation_id": _clip_text(raw.get("correlation_id"), 64),
        "field_changes": field_changes,
        "permission_changes": permission_changes,
        "truncated": truncated,
    }


def sanitize_fields(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    fields: dict[str, str] = {}
    for key, value in list(raw.items())[:40]:
        if _SENSITIVE_KEY_RE.search(str(key)):
            continue
        text = _clip_text(value, 512)
        if text is None:
            continue
        fields[str(key)[:64]] = text
    return fields


def bound_payload(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(payload, default=str)
    if len(encoded.encode("utf-8")) <= PAYLOAD_MAX_BYTES:
        return payload
    detail = payload.get("detail")
    if isinstance(detail, dict):
        detail = dict(detail)
        detail["truncated"] = True
        field_changes = list(detail.get("field_changes") or [])
        perms = detail.get("permission_changes")
        while field_changes and len(json.dumps(payload, default=str).encode("utf-8")) > PAYLOAD_MAX_BYTES:
            field_changes.pop()
            detail["field_changes"] = field_changes
            payload = {**payload, "detail": detail}
        if isinstance(perms, dict) and perms.get("kind") == "overwrites":
            items = list(perms.get("items") or [])
            while items and len(json.dumps(payload, default=str).encode("utf-8")) > PAYLOAD_MAX_BYTES:
                items.pop()
                perms = {**perms, "items": items}
                detail["permission_changes"] = perms
                payload = {**payload, "detail": detail}
        payload = {**payload, "detail": detail}
    if len(json.dumps(payload, default=str).encode("utf-8")) > PAYLOAD_MAX_BYTES:
        payload = {
            "description": _clip_text(payload.get("description"), 300) or "",
            "fields": {},
            "detail": {
                "schema_version": SCHEMA_VERSION,
                "truncated": True,
                "field_changes": [],
                "permission_changes": None,
            }
            if isinstance(payload.get("detail"), dict)
            else None,
        }
    return payload


def prepare_event_payload(raw: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    source = _redact_mapping(raw or {})
    if not isinstance(source, dict):
        source = {}
    detail = sanitize_detail(source.get("detail"))
    payload = {
        "description": _clip_text(source.get("description"), 1000) or "",
        "fields": sanitize_fields(source.get("fields")),
        "detail": detail,
    }
    payload = bound_payload(payload)
    detail = payload.get("detail")
    has_perms = False
    if isinstance(detail, dict):
        perms = detail.get("permission_changes")
        if isinstance(perms, dict):
            has_perms = bool(
                perms.get("granted")
                or perms.get("revoked")
                or perms.get("items")
                or perms.get("category_synced")
            )
    has_detail = isinstance(detail, dict) and (
        bool(detail.get("field_changes")) or has_perms
    )
    return payload, has_detail


def serialize_event_summary(row: Any) -> dict[str, Any]:
    payload = row.payload if isinstance(row.payload, dict) else {}
    created = row.created_at.isoformat() if getattr(row, "created_at", None) else ""
    return {
        "id": str(row.id),
        "source_event_id": row.source_event_id,
        "category": row.category or "server",
        "action": row.action or "",
        "description": payload.get("description") or "",
        "event_type": row.event_type,
        "actor_id": row.actor_id,
        "actor_name": row.actor_name,
        "created_at": created,
        "has_detail": bool(row.has_detail),
    }


def serialize_event_detail(row: Any) -> dict[str, Any]:
    summary = serialize_event_summary(row)
    payload = row.payload if isinstance(row.payload, dict) else {}
    detail = sanitize_detail(payload.get("detail")) if isinstance(payload.get("detail"), dict) else payload.get("detail")
    if detail is not None and not isinstance(detail, dict):
        detail = None
    if isinstance(payload.get("detail"), dict) and payload["detail"].get("schema_version") != SCHEMA_VERSION:
        detail = None
    legacy = detail is None
    target = detail.get("target") if isinstance(detail, dict) else None
    source = detail.get("source") if isinstance(detail, dict) else None
    reason = detail.get("reason") if isinstance(detail, dict) else None
    correlation_id = detail.get("correlation_id") if isinstance(detail, dict) else None
    summary.update(
        {
            "target": target,
            "source": source,
            "reason": reason,
            "correlation_id": correlation_id,
            "detail": detail,
            "legacy": legacy,
            "fields": sanitize_fields(payload.get("fields")),
        }
    )
    return summary
