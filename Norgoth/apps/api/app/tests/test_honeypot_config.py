"""Honeypot PUT preserves warning IDs and does not force-repost on no-op saves."""

from __future__ import annotations

from app.routes.honeypot import resolve_force_warning_repost
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
