"""Unit tests for ticket lifecycle logging helpers (pure, no Discord I/O)."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing bot.* without installing the package.
BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.ticket_log_fields import (  # noqa: E402
    build_closed_ticket_log_fields,
    build_opened_ticket_log_fields,
    discord_timestamp,
    is_ticket_already_closed,
)


def test_opened_ticket_log_fields_include_required_metadata() -> None:
    fields = build_opened_ticket_log_fields(
        number=7,
        opener_identity="Display (@user)",
        opener_id="123456789",
        opened_at="2026-08-09T12:00:00+00:00",
        panel_name="Support",
    )
    assert fields["🎫 Ticket"] == "#0007"
    assert fields["👤 Opened By"] == "Display (@user)"
    assert fields["🆔 User ID"] == "123456789"
    assert fields["🕒 Opened At"] == discord_timestamp("2026-08-09T12:00:00+00:00")
    assert fields["🗂️ Panel"] == "Support"
    assert "Ticket Channel" not in fields
    assert not any("<#" in value for value in fields.values())


def test_opened_ticket_log_fields_omit_channel_mention_param() -> None:
    """channel_mention is no longer accepted — durable IDs only."""

    fields = build_opened_ticket_log_fields(
        number=1,
        opener_identity="User",
        opener_id="1",
        opened_at="2026-08-09T12:00:00+00:00",
    )
    assert "Ticket Channel" not in fields


def test_closed_ticket_log_fields_include_lifecycle_and_transcript() -> None:
    url = "http://127.0.0.1:3000/en/tickets/transcript/abc123"
    fields = build_closed_ticket_log_fields(
        number=12,
        opener_name="Display (@user)",
        closed_by="Mod (@mod)",
        channel_name="ticket-0012",
        transcript_url=url,
        opened_at="2026-08-09T12:00:00+00:00",
        closed_at="2026-08-09T13:00:00+00:00",
        panel_name="Support",
    )
    assert fields["🎫 Ticket"] == "#0012"
    assert fields["👤 Opened By"] == "Display (@user)"
    assert fields["🛡️ Closed By"] == "Mod (@mod)"
    assert fields["📝 Channel Name"] == "ticket-0012"
    assert fields["🕒 Opened At"] == discord_timestamp("2026-08-09T12:00:00+00:00")
    assert fields["🕒 Closed At"] == discord_timestamp("2026-08-09T13:00:00+00:00")
    assert fields["🗂️ Panel"] == "Support"
    assert fields["📄 Transcript"] == f"[View transcript]({url})"
    assert "Ticket Channel" not in fields


def test_closed_ticket_log_omits_channel_name_when_missing() -> None:
    fields = build_closed_ticket_log_fields(
        number=3,
        opener_name=None,
        closed_by="staff",
        channel_name=None,
        transcript_url="https://example.com/t",
    )
    assert "📝 Channel Name" not in fields
    assert fields["👤 Opened By"] == "unknown"


def test_close_idempotency_guard() -> None:
    assert is_ticket_already_closed({"status": "closed"}) is True
    assert is_ticket_already_closed({"status": "open"}) is False
    assert is_ticket_already_closed({}) is False
