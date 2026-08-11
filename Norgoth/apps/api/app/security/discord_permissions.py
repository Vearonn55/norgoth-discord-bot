"""Discord permission helpers for operator guild authorization."""

from __future__ import annotations

from urllib.parse import urlencode

ADMINISTRATOR = 1 << 3  # 0x8
MANAGE_GUILD = 1 << 5  # 0x20

DISCORD_OAUTH_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
BOT_INSTALL_SCOPES = "bot applications.commands"


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


def build_bot_invite_url(
    *,
    client_id: str,
    permissions: int = BOT_INVITE_PERMISSIONS_MINIMAL,
    guild_id: str | None = None,
) -> str:
    """Build a simple Discord Guild Install URL (not login OAuth).

    Uses ``bot`` + ``applications.commands`` only — no ``response_type=code``.
    When ``guild_id`` is set, Discord preselects that guild and
    ``disable_guild_select=true`` locks the picker.
    """

    params: dict[str, str] = {
        "client_id": client_id,
        "permissions": str(permissions),
        "scope": BOT_INSTALL_SCOPES,
    }
    if guild_id:
        params["guild_id"] = guild_id
        params["disable_guild_select"] = "true"
    return f"{DISCORD_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


__all__ = [
    "ADMINISTRATOR",
    "MANAGE_GUILD",
    "BOT_INSTALL_SCOPES",
    "BOT_INVITE_PERMISSIONS_MINIMAL",
    "build_bot_invite_url",
    "can_manage_guild",
]
