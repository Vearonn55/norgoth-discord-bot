"""Verification REST log embed title emojis and empty-field skip.

Tiny copy of the bot helper — the API cannot import ``bot.logging_presentation``.
Keep this subset in sync with verification keys in the bot ``LOG_EVENT_EMOJI`` map.
"""

from __future__ import annotations

from typing import Any

VERIFICATION_LOG_EMOJI: dict[str, str] = {
    "verification_succeeded": "✅",
    "verification_succeeded_role_pending": "✅",
    "verification_manual_review_required": "⚠️",
    "verification_denied": "❌",
    "verification_manual_decision": "❌",
}

_EMPTY_VALUES = frozenset({"", "#unknown", "—", "-"})


def apply_log_title_emoji(event_type: str, title: str) -> str:
    """Prefix the catalog emoji unless the title already starts with it."""

    emoji = VERIFICATION_LOG_EMOJI.get(event_type)
    if not emoji:
        return title
    stripped = title.lstrip()
    if stripped.startswith(emoji):
        return title
    return f"{emoji} {title}"


def filter_log_embed_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop fields whose value is empty, ``#unknown``, em dash, or hyphen."""

    out: list[dict[str, Any]] = []
    for field in fields:
        value = str(field.get("value") or "").strip()
        if value.lower() in _EMPTY_VALUES:
            continue
        out.append(field)
    return out
