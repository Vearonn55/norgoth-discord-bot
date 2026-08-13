"""Tests for the logging event catalog and config-driven colour resolution."""

from __future__ import annotations

from app.models.logging_config import LoggingChannel, LoggingEventMapping
from app.routes.logging_config import _effective_color
from app.services.logging_events import (
    EVENT_GROUPS,
    GROUP_DEFAULT_COLORS,
    all_event_types,
    catalog_payload,
    group_for_event,
)


def test_all_event_types_are_unique_and_nonempty() -> None:
    types = all_event_types()
    assert types
    # Every catalog event resolves back to exactly one group.
    for event_type in types:
        assert group_for_event(event_type) is not None


def test_group_for_event_known_and_unknown() -> None:
    assert group_for_event("member_join") == "member"
    assert group_for_event("mod_ban") == "moderation"
    assert group_for_event("does_not_exist") is None


def test_thread_and_security_events_resolve_to_groups() -> None:
    assert group_for_event("thread_create") == "thread"
    assert group_for_event("thread_delete") == "thread"
    assert group_for_event("thread_update") == "thread"
    assert group_for_event("honeypot_triggered") == "security"
    assert group_for_event("automod_action") == "security"
    assert group_for_event("raid_detected") == "security"
    assert group_for_event("member_kick") == "member"


def test_new_groups_have_default_colors() -> None:
    assert "thread" in GROUP_DEFAULT_COLORS
    assert "security" in GROUP_DEFAULT_COLORS
    # Every group referenced by an event must have a default colour.
    for event_type in all_event_types():
        group = group_for_event(event_type)
        assert group in GROUP_DEFAULT_COLORS


def test_tickets_group_is_registered() -> None:
    # Ticket open/close now flow through the central logging wizard.
    assert "tickets" in EVENT_GROUPS
    assert "tickets" in GROUP_DEFAULT_COLORS
    assert group_for_event("ticket_opened") == "tickets"
    assert group_for_event("ticket_closed") == "tickets"


def test_invites_group_is_registered() -> None:
    assert "invites" in EVENT_GROUPS
    assert "invites" in GROUP_DEFAULT_COLORS
    assert group_for_event("invite_member_joined") == "invites"
    assert group_for_event("invite_member_left") == "invites"
    labels = dict(EVENT_GROUPS["invites"]["events"])
    assert "invite_member_joined" in labels
    assert "invite_member_left" in labels


def test_verification_group_is_registered() -> None:
    assert "verification" in EVENT_GROUPS
    assert "verification" in GROUP_DEFAULT_COLORS
    assert group_for_event("verification_succeeded") == "verification"
    assert group_for_event("verification_denied") == "verification"
    assert group_for_event("verification_manual_decision") == "verification"
    labels = dict(EVENT_GROUPS["verification"]["events"])
    assert "verification_succeeded_role_pending" in labels
    assert "verification_manual_review_required" in labels


def test_catalog_payload_shape_matches_wizard_contract() -> None:
    payload = catalog_payload()
    assert set(payload) == {"groups"}
    keys = {group["key"] for group in payload["groups"]}
    assert keys == set(EVENT_GROUPS)
    for group in payload["groups"]:
        assert group["default_color"] == GROUP_DEFAULT_COLORS.get(group["key"])
        assert group["events"], "each group exposes at least one event"
        for event in group["events"]:
            assert set(event) == {"event_type", "label"}


def test_effective_color_precedence() -> None:
    channel = LoggingChannel(
        guild_id="1",
        key="member",
        name="member-log",
        default_color=0x111111,
        position=0,
    )

    # 1) explicit per-event override wins.
    override = LoggingEventMapping(
        guild_id="1", event_type="member_join", color=0x222222, enabled=True
    )
    assert _effective_color(override, channel) == 0x222222

    # 2) channel default is used when the event has no override.
    inherit = LoggingEventMapping(
        guild_id="1", event_type="member_join", color=None, enabled=True
    )
    assert _effective_color(inherit, channel) == 0x111111

    # 3) group default is used when neither event nor channel specify a colour.
    no_channel = LoggingEventMapping(
        guild_id="1", event_type="member_join", color=None, enabled=True
    )
    assert _effective_color(no_channel, None) == GROUP_DEFAULT_COLORS["member"]

    # 4) unknown events with no colour anywhere resolve to None.
    unknown = LoggingEventMapping(
        guild_id="1", event_type="mystery_event", color=None, enabled=True
    )
    assert _effective_color(unknown, None) is None
