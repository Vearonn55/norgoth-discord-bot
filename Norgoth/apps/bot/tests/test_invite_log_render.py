"""Unit tests for invite log render helpers (pure, no Discord I/O)."""

from __future__ import annotations

import sys
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.invite_log_render import (  # noqa: E402
    attribution_status,
    build_invite_log_fields,
    build_template_context,
    discord_timestamp,
    render_invite_log_description,
    sanitize_template_text,
    validate_template,
)


def test_attribution_status() -> None:
    assert attribution_status("vanity", None) == "vanity"
    assert attribution_status("abc", "123") == "attributed"
    assert attribution_status(None, None) == "unknown"


def test_join_fields_attributed() -> None:
    fields = build_invite_log_fields(
        kind="join",
        member_name="Alice",
        member_id="1",
        inviter_id="2",
        inviter_name="Bob",
        inviter_count=5,
        invite_code="abc12",
        joined_at="2026-08-09T12:00:00+00:00",
    )
    assert fields["Event"] == "Member Joined"
    assert fields["Invited By"] == "<@2>"
    assert fields["Inviter Total Invites"] == "5"
    assert fields["Invitation Source"] == "abc12"
    assert fields["Joined At"].startswith("<t:")


def test_leave_fields_unknown() -> None:
    fields = build_invite_log_fields(
        kind="leave",
        member_name="Alice",
        member_id="1",
        inviter_id=None,
        inviter_name=None,
        inviter_count=None,
        invite_code=None,
        joined_at=None,
        left_at="2026-08-09T13:00:00+00:00",
    )
    assert fields["Original Inviter"] == "Unknown"
    assert fields["Inviter Total Invites"] == "—"
    assert fields["Invitation Source"] == "Unknown"
    assert "null" not in fields["Original Inviter"].lower()


def test_vanity_fields() -> None:
    fields = build_invite_log_fields(
        kind="join",
        member_name="Alice",
        member_id="1",
        inviter_id=None,
        inviter_name=None,
        inviter_count=None,
        invite_code="vanity",
        joined_at=None,
    )
    assert fields["Invited By"] == "Vanity URL"
    assert fields["Invitation Source"] == "Vanity URL"


def test_consumed_one_use_fields_and_stored_attribution() -> None:
    fields = build_invite_log_fields(
        kind="join",
        member_name="Alice",
        member_id="1",
        inviter_id="2",
        inviter_name="Bob",
        inviter_count=3,
        invite_code="oneuse",
        joined_at=None,
        attribution="consumed_one_use",
    )
    assert fields["Invited By"] == "<@2>"
    assert fields["Invitation Source"] == "Single-use invitation (oneuse)"
    assert fields["Inviter Total Invites"] == "3"
    assert attribution_status("oneuse", "2", stored="consumed_one_use") == (
        "consumed_one_use"
    )


def test_template_render_and_sanitization() -> None:
    ctx = build_template_context(
        kind="join",
        guild_name="Guild",
        member_id="1",
        member_name="Alice",
        inviter_id="2",
        inviter_name="Bob",
        inviter_count=4,
        invite_code="xyz",
        joined_at=None,
    )
    text = render_invite_log_description(
        kind="join",
        template="@everyone {user_mention} by {inviter_mention} ({inviter_count})",
        context=ctx,
    )
    assert "@everyone" not in text
    assert "<@1>" in text
    assert "<@2>" in text
    assert "4" in text


def test_validate_unknown_placeholder() -> None:
    errors = validate_template("{nope}", kind="join")
    assert errors


def test_discord_timestamp_invalid() -> None:
    assert discord_timestamp("not-a-date") == "—"
    assert sanitize_template_text("ping @here now").find("@here") == -1 or "\u200b" in sanitize_template_text(
        "ping @here now"
    )
