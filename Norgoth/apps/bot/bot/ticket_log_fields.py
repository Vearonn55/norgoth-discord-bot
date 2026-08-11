"""Pure helpers for ticket lifecycle logging embeds.

Kept free of discord.py imports so unit tests can exercise field construction
and the close idempotency guard without a Discord runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def discord_timestamp(iso_or_dt: str | datetime | None) -> str:
    """Render a Discord absolute timestamp token, or em dash."""

    if iso_or_dt is None or iso_or_dt == "":
        return "—"
    if isinstance(iso_or_dt, datetime):
        dt = iso_or_dt
    else:
        raw = str(iso_or_dt).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f"<t:{int(dt.timestamp())}:f>"


def build_opened_ticket_log_fields(
    *,
    number: int,
    opener_identity: str,
    opener_id: str,
    opened_at: str,
    panel_name: str | None = None,
) -> dict[str, str]:
    """Structured fields for the Ticket Opened logging embed.

    Durable identifiers only — never include a live channel mention (those
    become ``#unknown`` after the ticket channel is deleted on close).
    """

    fields: dict[str, str] = {
        "🎫 Ticket": f"#{number:04d}",
        "👤 Opened By": opener_identity,
        "🆔 User ID": opener_id,
        "🕒 Opened At": discord_timestamp(opened_at),
    }
    if panel_name:
        fields["🗂️ Panel"] = panel_name
    return fields


def build_closed_ticket_log_fields(
    *,
    number: Any,
    opener_name: str | None,
    closed_by: str,
    channel_name: str | None,
    transcript_url: str,
    opened_at: str | None = None,
    closed_at: str | None = None,
    panel_name: str | None = None,
) -> dict[str, str]:
    """Structured fields for the Ticket Closed logging embed."""

    try:
        ticket_label = f"#{int(number):04d}"
    except (TypeError, ValueError):
        ticket_label = f"#{number}"

    fields: dict[str, str] = {
        "🎫 Ticket": ticket_label,
        "👤 Opened By": opener_name or "unknown",
        "🛡️ Closed By": closed_by,
        "📄 Transcript": f"[View transcript]({transcript_url})",
    }
    if channel_name:
        fields["📝 Channel Name"] = channel_name
    if opened_at:
        fields["🕒 Opened At"] = discord_timestamp(opened_at)
    if closed_at:
        fields["🕒 Closed At"] = discord_timestamp(closed_at)
    if panel_name:
        fields["🗂️ Panel"] = panel_name
    return fields


def is_ticket_already_closed(record: dict[str, Any]) -> bool:
    """Idempotency guard for close retries."""

    return record.get("status") == "closed"
