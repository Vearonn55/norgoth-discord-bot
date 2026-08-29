"""Discord permission helpers for operator guild authorization."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlencode

ADMINISTRATOR = 1 << 3  # 0x8
MANAGE_CHANNELS = 1 << 4  # 0x10
MANAGE_GUILD = 1 << 5  # 0x20
VIEW_AUDIT_LOG = 1 << 7  # 0x80
VIEW_CHANNEL = 1 << 10  # 0x400
SEND_MESSAGES = 1 << 11  # 0x800
EMBED_LINKS = 1 << 14  # 0x4000
READ_MESSAGE_HISTORY = 1 << 16  # 0x10000
MANAGE_ROLES = 1 << 28  # 0x10000000

# Match Discord Developer Portal Guild Install links (not /api/oauth2).
DISCORD_OAUTH_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
BOT_INSTALL_SCOPES = "bot applications.commands"
# Discord install contexts: 0 = Guild Install, 1 = User Install.
DISCORD_INTEGRATION_TYPE_GUILD = "0"


def can_manage_guild(*, owner: bool, permissions: str | int) -> bool:
    """Return True when the user may manage the guild in Norgoth."""

    if owner:
        return True
    try:
        bits = int(permissions)
    except (TypeError, ValueError):
        return False
    return bool(bits & ADMINISTRATOR) or bool(bits & MANAGE_GUILD)


def guild_role_label(*, owner: bool, permissions: str | int) -> str:
    """Return Owner, Administrator, or Manage Server from Discord bits."""

    if owner:
        return "Owner"
    try:
        bits = int(permissions)
    except (TypeError, ValueError):
        return "Manage Server"
    if bits & ADMINISTRATOR:
        return "Administrator"
    return "Manage Server"


# Minimum practical bot invite permissions for shipped features.
BOT_INVITE_PERMISSIONS = (
    ADMINISTRATOR  # temporary practical default for invite URL only when needed
)
# Prefer non-Administrator bitmask for production invite CTA:
BOT_INVITE_PERMISSIONS_MINIMAL = (
    VIEW_CHANNEL
    | SEND_MESSAGES
    | EMBED_LINKS
    | (1 << 13)  # MANAGE_MESSAGES
    | (1 << 1)  # KICK_MEMBERS
    | (1 << 2)  # BAN_MEMBERS
    | (1 << 40)  # MODERATE_MEMBERS
    | MANAGE_CHANNELS
    | MANAGE_ROLES
    | MANAGE_GUILD
    | VIEW_AUDIT_LOG
    | (1 << 15)  # ATTACH_FILES
    | READ_MESSAGE_HISTORY
    | (1 << 17)  # MENTION_EVERYONE (for ping roles in security alerts)
    | (1 << 29)  # MANAGE_WEBHOOKS (content notifications)
)

# Labels shown in logging health. Existing guilds must be granted View Audit Log.
LOGGING_REQUIRED_PERMISSIONS: tuple[tuple[str, int], ...] = (
    ("View Audit Log", VIEW_AUDIT_LOG),
    ("Manage Server", MANAGE_GUILD),
    ("Manage Channels", MANAGE_CHANNELS),
    ("View Channels", VIEW_CHANNEL),
    ("Send Messages", SEND_MESSAGES),
)


def compute_member_permissions(
    *,
    guild_id: str,
    owner_id: str | None,
    member_user_id: str | None,
    member_roles: Iterable[str],
    roles: Iterable[dict[str, Any]],
) -> int:
    """OR role permission bits for a guild member, including @everyone."""

    if owner_id and member_user_id and str(owner_id) == str(member_user_id):
        return (
            ADMINISTRATOR
            | VIEW_AUDIT_LOG
            | MANAGE_GUILD
            | MANAGE_CHANNELS
            | VIEW_CHANNEL
            | SEND_MESSAGES
        )

    by_id: dict[str, dict[str, Any]] = {}
    for role in roles:
        if not isinstance(role, dict):
            continue
        role_id = role.get("id")
        if role_id is None:
            continue
        by_id[str(role_id)] = role

    bits = 0
    seen: set[str] = set()
    for role_id in (str(guild_id), *[str(item) for item in member_roles]):
        if role_id in seen:
            continue
        seen.add(role_id)
        role = by_id.get(role_id)
        if role is None:
            continue
        try:
            bits |= int(role.get("permissions") or 0)
        except (TypeError, ValueError):
            continue
    if bits & ADMINISTRATOR:
        bits |= (
            VIEW_AUDIT_LOG
            | MANAGE_GUILD
            | MANAGE_CHANNELS
            | VIEW_CHANNEL
            | SEND_MESSAGES
        )
    return bits


def missing_logging_permissions(bits: int) -> list[str]:
    return [
        label
        for label, mask in LOGGING_REQUIRED_PERMISSIONS
        if not (bits & mask)
    ]


def build_bot_invite_url(
    *,
    client_id: str,
    permissions: int = BOT_INVITE_PERMISSIONS_MINIMAL,
    guild_id: str | None = None,
) -> str:
    """Build a simple Discord Guild Install URL (not login OAuth).

    Mirrors the Developer Portal generator for Guild Install:
    ``bot`` + ``applications.commands`` + ``integration_type=0``,
    with no ``response_type`` / ``redirect_uri``.
    When ``guild_id`` is set, Discord preselects that guild and
    ``disable_guild_select=true`` locks the picker.
    """

    params: dict[str, str] = {
        "client_id": client_id,
        "permissions": str(permissions),
        "integration_type": DISCORD_INTEGRATION_TYPE_GUILD,
        "scope": BOT_INSTALL_SCOPES,
    }
    if guild_id:
        params["guild_id"] = guild_id
        params["disable_guild_select"] = "true"
    return f"{DISCORD_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


__all__ = [
    "ADMINISTRATOR",
    "EMBED_LINKS",
    "MANAGE_CHANNELS",
    "MANAGE_GUILD",
    "MANAGE_ROLES",
    "READ_MESSAGE_HISTORY",
    "SEND_MESSAGES",
    "VIEW_AUDIT_LOG",
    "VIEW_CHANNEL",
    "BOT_INSTALL_SCOPES",
    "BOT_INVITE_PERMISSIONS_MINIMAL",
    "DISCORD_INTEGRATION_TYPE_GUILD",
    "LOGGING_REQUIRED_PERMISSIONS",
    "build_bot_invite_url",
    "can_manage_guild",
    "compute_member_permissions",
    "guild_role_label",
    "missing_logging_permissions",
]
