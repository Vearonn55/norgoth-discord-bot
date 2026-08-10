"""Shared campaign / template variable resolution helpers."""

from __future__ import annotations

from typing import Any

# Neutral fallback when no Discord user context is available (channel campaigns,
# or a recipient record missing both display_name and name). Matches the DM
# campaign missing-name policy — never a greeting like "there".
USER_NAME_FALLBACK = "member"


def resolve_user_name(
    *,
    display_name: str | None = None,
    name: str | None = None,
    fallback: str = USER_NAME_FALLBACK,
) -> str:
    """Resolve ``{user_name}`` for campaign (and similar) templates.

    Preference order: display_name → name → fallback.
    """

    for candidate in (display_name, name):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return fallback


def resolve_user_name_from_recipient(recipient: dict[str, Any] | None) -> str:
    """Resolve ``{user_name}`` from a guild member / recipient snapshot dict."""

    if not isinstance(recipient, dict):
        return USER_NAME_FALLBACK
    return resolve_user_name(
        display_name=recipient.get("display_name")
        if isinstance(recipient.get("display_name"), str)
        else None,
        name=recipient.get("name") if isinstance(recipient.get("name"), str) else None,
    )
