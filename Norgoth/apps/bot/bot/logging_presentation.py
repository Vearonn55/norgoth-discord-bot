"""Log embed title emojis and field layout — Discord-free for unit tests."""

from __future__ import annotations

from typing import Any

LOG_EVENT_EMOJI: dict[str, str] = {
    "member_join": "👋",
    "member_leave": "👋",
    "member_kick": "👢",
    "member_ban": "🔨",
    "member_unban": "🔓",
    "member_nickname": "📝",
    "member_roles_update": "🏷️",
    "member_timeout": "⏳",
    "member_timeout_clear": "✅",
    "message_edit": "✏️",
    "message_delete": "🗑️",
    "message_delete_raw": "🗑️",
    "message_bulk_delete": "🗑️",
    "message_reaction_add": "➕",
    "message_reaction_remove": "➖",
    "channel_create": "➕",
    "channel_delete": "🗑️",
    "channel_update": "✏️",
    "channel_pins_update": "📌",
    "role_create": "🏷️",
    "role_delete": "🗑️",
    "role_update": "✏️",
    "guild_update": "⚙️",
    "guild_emojis_update": "😀",
    "guild_stickers_update": "😀",
    "webhooks_update": "🔗",
    "voice_join": "🔊",
    "voice_leave": "🔇",
    "voice_move": "🔀",
    "voice_server_mute": "🔇",
    "voice_server_deafen": "🔇",
    "voice_stream": "📺",
    "thread_create": "➕",
    "thread_delete": "🗑️",
    "thread_update": "✏️",
    "thread_member_join": "👋",
    "thread_member_remove": "👋",
    "mod_kick": "👢",
    "mod_ban": "🔨",
    "mod_timeout": "⏳",
    "mod_purge": "🧹",
    "mod_warn": "⚠️",
    "honeypot_triggered": "🛡️",
    "honeypot_member_detected": "🛡️",
    "honeypot_punishment_applied": "🛡️",
    "automod_action": "🛡️",
    "discord_automod_execution": "🛡️",
    "raid_detected": "🛡️",
    "ticket_opened": "🎫",
    "ticket_closed": "🔒",
    "invite_member_joined": "✉️",
    "invite_created": "✉️",
    "invite_member_left": "➖",
    "invite_deleted": "➖",
    "verification_succeeded": "✅",
    "verification_succeeded_role_pending": "✅",
    "verification_manual_review_required": "⚠️",
    "verification_denied": "❌",
    "verification_manual_decision": "❌",
}

TITLE_LIMIT = 256
DESCRIPTION_LIMIT = 4096
FOOTER_LIMIT = 2048
FIELD_NAME_LIMIT = 256
FIELD_VALUE_LIMIT = 1024
MAX_FIELDS = 20
EMBED_TOTAL_LIMIT = 6000

_EMPTY_VALUES = frozenset({"", "#unknown", "—", "-"})

_NON_INLINE_TOKENS = (
    "member",
    "channel",
    "role",
    "ticket",
    "target",
    "reason",
    "content",
    "before",
    "after",
    "opened by",
    "closed by",
    "transcript",
    "granted",
    "revoked",
    "denied",
    "inherited",
    "overwrite",
    "sync",
)


def apply_log_title_emoji(event_type: str, title: str) -> str:
    """Prefix the catalog emoji unless the title already starts with it."""

    emoji = LOG_EVENT_EMOJI.get(event_type)
    if not emoji:
        return title
    stripped = title.lstrip()
    if stripped.startswith(emoji):
        return title
    return f"{emoji} {title}"


def _plain_field_name(name: str) -> str:
    parts = name.strip().split(" ", 1)
    if len(parts) == 2 and not parts[0].isascii():
        return parts[1]
    return name.strip()


def _is_empty_field_value(value: str) -> bool:
    return value.strip().lower() in _EMPTY_VALUES


def field_is_inline(name: str) -> bool:
    lowered = _plain_field_name(name).lower()
    if lowered.endswith(" id") or lowered.endswith("_id"):
        return True
    return not any(token in lowered for token in _NON_INLINE_TOKENS)


def _field_drop_priority(name: str) -> int:
    """Lower numbers are dropped first when clamping the 6000-character budget."""

    lowered = _plain_field_name(name).lower()
    if lowered.endswith(" id") or lowered.endswith("_id") or lowered.endswith("id"):
        return 0
    return 1


def _total_characters(
    title: str,
    description: str,
    footer: str,
    fields: list[tuple[str, str, bool]],
) -> int:
    total = len(title) + len(description) + len(footer)
    for name, value, _inline in fields:
        total += len(name) + len(value)
    return total


def compose_log_fields(
    fields: dict[str, str] | None,
    *,
    title: str = "",
    description: str = "",
    footer: str = "",
) -> list[tuple[str, str, bool]]:
    """Skip empty values, assign inline layout, cap count and total characters."""

    composed: list[tuple[str, str, bool]] = []
    for key, raw in list((fields or {}).items()):
        name = str(key)[:FIELD_NAME_LIMIT]
        value = str(raw)[:FIELD_VALUE_LIMIT]
        if _is_empty_field_value(value):
            continue
        composed.append((name, value, field_is_inline(name)))

    composed = composed[:MAX_FIELDS]
    while composed and _total_characters(title, description, footer, composed) > EMBED_TOTAL_LIMIT:
        drop_at = min(
            range(len(composed)),
            key=lambda index: (_field_drop_priority(composed[index][0]), -index),
        )
        composed.pop(drop_at)
    return composed


def compose_log_embed_spec(
    title: str,
    description: str,
    *,
    fields: dict[str, str] | None = None,
    footer: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    titled = apply_log_title_emoji(event_type, title) if event_type else title
    titled = titled[:TITLE_LIMIT]
    desc = (description or "")[:DESCRIPTION_LIMIT]
    foot = (footer or "")[:FOOTER_LIMIT]
    return {
        "title": titled,
        "description": desc,
        "footer": foot or None,
        "fields": compose_log_fields(
            fields, title=titled, description=desc, footer=foot
        ),
    }
