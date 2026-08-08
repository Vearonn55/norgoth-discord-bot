"""Catalog of loggable Discord event types, grouped for the setup wizard.

This is the single source of truth the dashboard wizard uses to render event
groups, and the default colours applied when a guild does not override them.
Colours are Discord decimal integers.
"""

from __future__ import annotations

from typing import Any

# Default embed colour per group (Discord decimal integers).
GROUP_DEFAULT_COLORS: dict[str, int] = {
    "member": 0x2ECC71,
    "message": 0x3498DB,
    "channel": 0x95A5A6,
    "role": 0xE67E22,
    "server": 0x9B59B6,
    "voice": 0x1ABC9C,
    "thread": 0x11806A,
    "moderation": 0xE74C3C,
    "security": 0xC0392B,
}

# group key -> (label, [(event_type, label), ...])
EVENT_GROUPS: dict[str, dict[str, Any]] = {
    "member": {
        "label": "Members",
        "events": [
            ("member_join", "Member joined"),
            ("member_leave", "Member left"),
            ("member_ban", "Member banned"),
            ("member_unban", "Member unbanned"),
            ("member_nickname", "Nickname changed"),
            ("member_roles_update", "Member roles changed"),
            ("member_timeout", "Member timed out"),
        ],
    },
    "message": {
        "label": "Messages",
        "events": [
            ("message_edit", "Message edited"),
            ("message_delete", "Message deleted"),
            ("message_bulk_delete", "Messages bulk deleted"),
        ],
    },
    "channel": {
        "label": "Channels",
        "events": [
            ("channel_create", "Channel created"),
            ("channel_delete", "Channel deleted"),
            ("channel_update", "Channel updated"),
        ],
    },
    "role": {
        "label": "Roles",
        "events": [
            ("role_create", "Role created"),
            ("role_delete", "Role deleted"),
            ("role_update", "Role updated"),
        ],
    },
    "server": {
        "label": "Server",
        "events": [
            ("guild_update", "Server settings updated"),
        ],
    },
    "voice": {
        "label": "Voice",
        "events": [
            ("voice_join", "Joined voice"),
            ("voice_leave", "Left voice"),
            ("voice_move", "Moved voice channel"),
        ],
    },
    "thread": {
        "label": "Threads",
        "events": [
            ("thread_create", "Thread created"),
            ("thread_delete", "Thread deleted"),
            ("thread_update", "Thread updated"),
        ],
    },
    "moderation": {
        "label": "Moderation",
        "events": [
            ("mod_kick", "Kick"),
            ("mod_ban", "Ban"),
            ("mod_timeout", "Timeout"),
            ("mod_purge", "Purge"),
            ("mod_warn", "Warn"),
            ("member_kick", "Member kicked"),
        ],
    },
    "security": {
        "label": "Security",
        "events": [
            ("honeypot_triggered", "Honeypot triggered"),
            ("honeypot_member_detected", "Honeypot member detected"),
            ("honeypot_punishment_applied", "Honeypot punishment applied"),
            ("automod_action", "Auto-moderation action"),
            ("raid_detected", "Raid detected"),
        ],
    },
}


def all_event_types() -> set[str]:
    types: set[str] = set()
    for group in EVENT_GROUPS.values():
        for event_type, _label in group["events"]:
            types.add(event_type)
    return types


def group_for_event(event_type: str) -> str | None:
    for key, group in EVENT_GROUPS.items():
        for candidate, _label in group["events"]:
            if candidate == event_type:
                return key
    return None


def catalog_payload() -> dict[str, Any]:
    """Serialise the catalog for the dashboard wizard."""

    return {
        "groups": [
            {
                "key": key,
                "label": group["label"],
                "default_color": GROUP_DEFAULT_COLORS.get(key),
                "events": [
                    {"event_type": event_type, "label": label}
                    for event_type, label in group["events"]
                ],
            }
            for key, group in EVENT_GROUPS.items()
        ]
    }
