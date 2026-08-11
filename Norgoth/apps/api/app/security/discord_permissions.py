"""Discord permission helpers for operator guild authorization."""

from __future__ import annotations

ADMINISTRATOR = 1 << 3  # 0x8
MANAGE_GUILD = 1 << 5  # 0x20


def can_manage_guild(*, owner: bool, permissions: str | int) -> bool:
    """Return True when the user may manage the guild in Norgoth."""

    if owner:
        return True
    try:
        bits = int(permissions)
    except (TypeError, ValueError):
        return False
    return bool(bits & ADMINISTRATOR) or bool(bits & MANAGE_GUILD)


# Minimum practical bot invite permissions for shipped features.
BOT_INVITE_PERMISSIONS = (
    ADMINISTRATOR  # temporary practical default for invite URL only when needed
)
# Prefer non-Administrator bitmask for production invite CTA:
BOT_INVITE_PERMISSIONS_MINIMAL = (
    (1 << 10)  # VIEW_CHANNEL
    | (1 << 11)  # SEND_MESSAGES
    | (1 << 14)  # EMBED_LINKS
    | (1 << 13)  # MANAGE_MESSAGES
    | (1 << 1)  # KICK_MEMBERS
    | (1 << 2)  # BAN_MEMBERS
    | (1 << 40)  # MODERATE_MEMBERS
    | (1 << 4)  # MANAGE_CHANNELS
    | (1 << 28)  # MANAGE_ROLES
    | (1 << 5)  # MANAGE_GUILD
    | (1 << 15)  # ATTACH_FILES
    | (1 << 16)  # READ_MESSAGE_HISTORY
    | (1 << 17)  # MENTION_EVERYONE (for ping roles in security alerts)
    | (1 << 29)  # MANAGE_WEBHOOKS (content notifications)
)


__all__ = [
    "ADMINISTRATOR",
    "MANAGE_GUILD",
    "BOT_INVITE_PERMISSIONS_MINIMAL",
    "can_manage_guild",
]
