"""Honeypot PUT preserves warning IDs and does not force-repost on no-op saves."""

from __future__ import annotations

import json

from app.routes.honeypot import (
    exemption_audit_changes,
    parse_member_snapshot,
    resolve_force_warning_repost,
    validate_exempt_member_ids,
)
from app.services.feature_config_store import merge_honeypot_warning_fields


def test_put_without_trap_change_does_not_force_repost() -> None:
    existing = {
        "trap_channel_ids": ["111111111111111111"],
        "post_pinned_warning": True,
        "warning_message_id": "555",
        "warning_channel_id": "111111111111111111",
    }
    payload = {
        "trap_channel_ids": ["111111111111111111"],
        "post_pinned_warning": True,
        "enabled": True,
    }
    assert resolve_force_warning_repost(existing, payload) is False


def test_put_merge_keeps_warning_message_id() -> None:
    existing = {
        "trap_channel_ids": ["111111111111111111"],
        "warning_message_id": "555",
        "warning_channel_id": "111111111111111111",
        "warning_pinned": True,
    }
    payload = {
        "enabled": False,
        "trap_channel_ids": ["111111111111111111"],
        "post_pinned_warning": True,
    }
    merged = merge_honeypot_warning_fields(existing, payload)
    assert merged["warning_message_id"] == "555"
    assert merged["warning_channel_id"] == "111111111111111111"
    assert merged["warning_pinned"] is True


def test_channel_change_or_empty_ids_forces_repost() -> None:
    existing = {
        "trap_channel_ids": ["111111111111111111"],
        "post_pinned_warning": True,
        "warning_message_id": "555",
    }
    moved = {
        "trap_channel_ids": ["222222222222222222"],
        "post_pinned_warning": True,
    }
    assert resolve_force_warning_repost(existing, moved) is True
    first = {"trap_channel_ids": ["111111111111111111"], "post_pinned_warning": True}
    assert resolve_force_warning_repost({}, first) is True


def test_validate_exempt_member_ids_keeps_stale_and_rejects_unknown_adds() -> None:
    snapshot = {"111", "222"}
    existing = ["999"]
    requested = ["111", "999", "333"]
    validated, rejected = validate_exempt_member_ids(existing, requested, snapshot)
    assert validated == ["111", "999"]
    assert rejected == ["333"]


def test_validate_exempt_member_ids_allows_all_when_snapshot_missing() -> None:
    validated, rejected = validate_exempt_member_ids(
        [],
        ["111", "222"],
        None,
    )
    assert validated == ["111", "222"]
    assert rejected == []


def test_parse_member_snapshot_extracts_ids() -> None:
    raw = json.dumps(
        {
            "members": [
                {"id": "111111111111111111", "name": "alpha"},
                {"id": "222222222222222222", "name": "beta"},
            ]
        }
    )
    assert parse_member_snapshot(raw) == {
        "111111111111111111",
        "222222222222222222",
    }


def test_exemption_audit_changes_detects_member_and_role_diffs() -> None:
    existing = {
        "exempt_member_ids": ["111"],
        "exempt_role_ids": ["999"],
    }
    payload = {
        "exempt_member_ids": ["111", "222"],
        "exempt_role_ids": ["999"],
    }
    changes = exemption_audit_changes(existing, payload)
    assert changes == {
        "exempt_member_ids": {
            "before": ["111"],
            "after": ["111", "222"],
        }
    }
