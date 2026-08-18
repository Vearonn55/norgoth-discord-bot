"""Pure helpers for invite join/leave logging embeds and templates.

Kept free of discord.py so unit tests can exercise rendering, validation, and
unknown/vanity fallbacks without a Discord runtime.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

AttributionStatus = Literal[
    "attributed",
    "vanity",
    "unknown",
    "consumed_one_use",
    "deleted",
    "ambiguous",
    "unavailable",
]

_CREDITED_STATUSES = frozenset({"attributed", "consumed_one_use", "deleted"})

JOIN_VARIABLES = frozenset(
    {
        "user",
        "username",
        "user_mention",
        "user_id",
        "inviter",
        "inviter_mention",
        "inviter_id",
        "inviter_count",
        "invite_code",
        "joined_at",
        "server",
    }
)

LEAVE_VARIABLES = frozenset(
    {
        *JOIN_VARIABLES,
        "left_at",
    }
)

DEFAULT_JOIN_MESSAGE = (
    "{user_mention} joined the server.\n"
    "Invited by {inviter_mention}.\n"
    "{inviter_mention} has {inviter_count} total invites."
)

DEFAULT_LEAVE_MESSAGE = (
    "{user_mention} left the server.\n"
    "They originally joined via {inviter_mention}.\n"
    "{inviter_mention} has {inviter_count} total invites."
)

_PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_]+)\}")
_UNSAFE_MENTION_RE = re.compile(r"@(everyone|here)\b", re.IGNORECASE)


def attribution_status(
    code: str | None,
    inviter_id: str | None,
    stored: str | None = None,
) -> str:
    if stored:
        return stored
    if code == "vanity":
        return "vanity"
    if inviter_id:
        return "attributed"
    return "unknown"


def discord_timestamp(iso_or_dt: str | datetime | None) -> str:
    """Render a Discord relative/absolute timestamp token, or em dash."""

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


def sanitize_template_text(text: str) -> str:
    """Strip mass-mention tokens from custom template content."""

    return _UNSAFE_MENTION_RE.sub("@\u200b\\1", text or "")


def validate_template(
    text: str,
    *,
    kind: Literal["join", "leave"],
    max_length: int = 4000,
) -> list[str]:
    """Return a list of validation errors (empty when valid)."""

    errors: list[str] = []
    value = text or ""
    if len(value) > max_length:
        errors.append(f"Message exceeds {max_length} characters.")

    allowed = JOIN_VARIABLES if kind == "join" else LEAVE_VARIABLES
    for match in _PLACEHOLDER_RE.finditer(value):
        token = match.group(1)
        if token not in allowed:
            errors.append(f"Unknown placeholder {{{token}}}.")
    return errors


def invite_source_label(code: str | None, status: str) -> str:
    if status == "vanity" or code == "vanity":
        return "Vanity URL"
    if status == "consumed_one_use":
        if code:
            return f"Single-use invitation ({code})"
        return "Single-use invitation"
    if code:
        return code
    return "Unknown"


def inviter_display(
    *,
    status: str,
    inviter_id: str | None,
    inviter_name: str | None,
    inviter_in_guild: bool | None = None,
) -> tuple[str, str]:
    """Return (display_name, mention_or_fallback) for the inviter."""

    if status == "vanity":
        return ("Vanity URL", "Vanity URL")
    if status in {"unknown", "ambiguous", "unavailable"} or not inviter_id:
        if status == "deleted" and not inviter_id:
            return ("Deleted invite", "Deleted invite")
        if status == "ambiguous":
            return ("Ambiguous", "Ambiguous")
        if status == "unavailable":
            return ("Unavailable", "Unavailable")
        return ("Unknown", "Unknown")

    name = (inviter_name or inviter_id).strip() or inviter_id
    if inviter_in_guild is False:
        name = f"Former member / {name}"
    mention = f"<@{inviter_id}>"
    return (name, mention)


def build_template_context(
    *,
    kind: Literal["join", "leave"],
    guild_name: str,
    member_id: str,
    member_name: str,
    member_username: str | None = None,
    inviter_id: str | None,
    inviter_name: str | None,
    inviter_count: int | None,
    invite_code: str | None,
    joined_at: str | None,
    left_at: str | None = None,
    inviter_in_guild: bool | None = None,
    attribution: str | None = None,
) -> dict[str, str]:
    status = attribution_status(invite_code, inviter_id, stored=attribution)
    inviter_label, inviter_mention = inviter_display(
        status=status,
        inviter_id=inviter_id,
        inviter_name=inviter_name,
        inviter_in_guild=inviter_in_guild,
    )
    username = member_username or member_name
    count = (
        str(inviter_count)
        if inviter_count is not None and status in _CREDITED_STATUSES
        else ("0" if status in _CREDITED_STATUSES else "—")
    )
    ctx: dict[str, str] = {
        "user": member_name,
        "username": username,
        "user_mention": f"<@{member_id}>",
        "user_id": member_id,
        "inviter": inviter_label,
        "inviter_mention": inviter_mention,
        "inviter_id": inviter_id or "—",
        "inviter_count": count,
        "invite_code": invite_source_label(invite_code, status),
        "joined_at": discord_timestamp(joined_at),
        "server": guild_name or "server",
    }
    if kind == "leave":
        ctx["left_at"] = discord_timestamp(left_at)
    return ctx


def render_template(template: str, context: dict[str, str]) -> str:
    """Substitute known placeholders; leave unknown tokens untouched (validated upstream)."""

    text = sanitize_template_text(template or "")

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return context[key]
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, text)


def render_invite_log_description(
    *,
    kind: Literal["join", "leave"],
    template: str | None,
    context: dict[str, str],
) -> str:
    raw = (template or "").strip()
    if not raw:
        raw = DEFAULT_JOIN_MESSAGE if kind == "join" else DEFAULT_LEAVE_MESSAGE
    return render_template(raw, context)[:4000]


def build_invite_log_fields(
    *,
    kind: Literal["join", "leave"],
    member_name: str,
    member_id: str,
    inviter_id: str | None,
    inviter_name: str | None,
    inviter_count: int | None,
    invite_code: str | None,
    joined_at: str | None,
    left_at: str | None = None,
    inviter_in_guild: bool | None = None,
    attribution: str | None = None,
) -> dict[str, str]:
    """Structured embed fields for invite join/leave logs."""

    status = attribution_status(invite_code, inviter_id, stored=attribution)
    inviter_label, inviter_mention = inviter_display(
        status=status,
        inviter_id=inviter_id,
        inviter_name=inviter_name,
        inviter_in_guild=inviter_in_guild,
    )
    fields: dict[str, str] = {
        "Event": "Member Joined" if kind == "join" else "Member Left",
        "Member": f"{member_name} (<@{member_id}>)",
        "Member ID": member_id,
    }
    if kind == "join":
        fields["Invited By"] = (
            inviter_mention if status in _CREDITED_STATUSES else inviter_label
        )
    else:
        fields["Original Inviter"] = (
            inviter_mention if status in _CREDITED_STATUSES else inviter_label
        )

    if status in _CREDITED_STATUSES:
        fields["Inviter Total Invites"] = str(
            inviter_count if inviter_count is not None else 0
        )
    else:
        fields["Inviter Total Invites"] = "—"

    fields["Invitation Source"] = invite_source_label(invite_code, status)
    fields["Joined At"] = discord_timestamp(joined_at)
    if kind == "leave":
        fields["Left At"] = discord_timestamp(left_at)
    return fields
