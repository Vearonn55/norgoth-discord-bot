"""Authoritative Discord application-command manifest for help, docs, and CI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

# Bump when the registered command set or option schema changes.
COMMAND_MANIFEST_VERSION = "2026-09-03.1"

Category = Literal[
    "General",
    "Info",
    "Levels",
    "Moderation",
    "Tickets",
    "Invites",
    "Verification",
    "Campaigns",
]


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    description: str
    category: Category
    module: str | None = None
    default_member_permissions: tuple[str, ...] = ()
    bot_permissions: tuple[str, ...] = ()
    visibility: Literal["ephemeral", "public", "channel"] = "ephemeral"
    cooldown_seconds: int | None = None
    command_type: Literal["chat", "user", "message"] = "chat"
    options: tuple[str, ...] = ()


COMMANDS: tuple[CommandSpec, ...] = (
    # Keep — hardened
    CommandSpec(
        name="kick",
        description="Kick a member from the server.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("kick_members",),
        bot_permissions=("kick_members",),
        options=("member", "reason?"),
    ),
    CommandSpec(
        name="ban",
        description="Ban a user from the server.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("ban_members",),
        bot_permissions=("ban_members",),
        options=("user", "reason?"),
    ),
    CommandSpec(
        name="timeout",
        description="Timeout a member for a number of minutes.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("moderate_members",),
        bot_permissions=("moderate_members",),
        options=("member", "minutes", "reason?"),
    ),
    CommandSpec(
        name="purge",
        description="Delete the last N messages in this channel.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("manage_messages",),
        bot_permissions=("manage_messages",),
        options=("amount",),
    ),
    CommandSpec(
        name="userinfo",
        description="Show info about a member.",
        category="Info",
        visibility="ephemeral",
        cooldown_seconds=3,
        options=("member?",),
    ),
    CommandSpec(
        name="rank",
        description="Show your (or a member's) level and XP.",
        category="Levels",
        module="leveling",
        visibility="public",
        options=("member?",),
    ),
    CommandSpec(
        name="give-xp",
        description="Grant XP to a member (Manage Server required).",
        category="Levels",
        module="leveling",
        default_member_permissions=("manage_guild",),
        visibility="public",
        options=("member", "amount"),
    ),
    CommandSpec(
        name="leaderboard",
        description="Show the server XP leaderboard.",
        category="Levels",
        module="leveling",
        visibility="public",
        options=("type?",),
    ),
    CommandSpec(
        name="role add",
        description="Give a role to a member.",
        category="Moderation",
        module="roles",
        default_member_permissions=("manage_roles",),
        bot_permissions=("manage_roles",),
        options=("member", "role"),
    ),
    CommandSpec(
        name="role remove",
        description="Remove a role from a member.",
        category="Moderation",
        module="roles",
        default_member_permissions=("manage_roles",),
        bot_permissions=("manage_roles",),
        options=("member", "role"),
    ),
    CommandSpec(
        name="ticket close",
        description="Close this ticket.",
        category="Tickets",
        module="tickets",
        bot_permissions=("manage_channels",),
        visibility="channel",
    ),
    CommandSpec(
        name="invites",
        description="Show how many members someone has invited.",
        category="Invites",
        module="invites",
        visibility="public",
        options=("member?",),
    ),
    CommandSpec(
        name="unsubscribe",
        description="Stop receiving campaign DMs from this server.",
        category="Campaigns",
        module="campaigns",
        visibility="ephemeral",
    ),
    # Phase 1
    CommandSpec(
        name="help",
        description="List NorBot commands available to you.",
        category="General",
        visibility="ephemeral",
        cooldown_seconds=5,
        options=("command?",),
    ),
    CommandSpec(
        name="dashboard",
        description="Open the NorBot dashboard for this server.",
        category="General",
        visibility="ephemeral",
        cooldown_seconds=5,
    ),
    CommandSpec(
        name="status",
        description="Show bot health for this server.",
        category="General",
        default_member_permissions=("manage_guild",),
        visibility="ephemeral",
        cooldown_seconds=10,
    ),
    CommandSpec(
        name="avatar",
        description="Show a user's avatar.",
        category="Info",
        visibility="public",
        cooldown_seconds=3,
        options=("user?", "type?"),
    ),
    CommandSpec(
        name="server",
        description="Show information about this server.",
        category="Info",
        visibility="public",
        cooldown_seconds=5,
    ),
    CommandSpec(
        name="roles",
        description="List roles in this server.",
        category="Info",
        visibility="ephemeral",
        cooldown_seconds=5,
    ),
    # Phase 2
    CommandSpec(
        name="unban",
        description="Remove a ban from a user.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("ban_members",),
        bot_permissions=("ban_members",),
        options=("user", "reason?"),
    ),
    CommandSpec(
        name="untimeout",
        description="Remove a timeout from a member.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("moderate_members",),
        bot_permissions=("moderate_members",),
        options=("member", "reason?"),
    ),
    CommandSpec(
        name="setnick",
        description="Set or clear a member's nickname.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("manage_nicknames",),
        bot_permissions=("manage_nicknames",),
        options=("member", "nickname?"),
    ),
    CommandSpec(
        name="vkick",
        description="Disconnect a member from voice.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("move_members",),
        bot_permissions=("move_members",),
        options=("member", "reason?"),
    ),
    CommandSpec(
        name="move",
        description="Move a member to a voice channel.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("move_members",),
        bot_permissions=("move_members",),
        options=("member", "channel"),
    ),
    CommandSpec(
        name="lock",
        description="Lock a text channel (deny @everyone Send Messages).",
        category="Moderation",
        module="moderation",
        default_member_permissions=("manage_channels",),
        bot_permissions=("manage_channels", "manage_roles"),
        options=("channel?", "reason?"),
    ),
    CommandSpec(
        name="unlock",
        description="Unlock a text channel.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("manage_channels",),
        bot_permissions=("manage_channels", "manage_roles"),
        options=("channel?", "reason?"),
    ),
    CommandSpec(
        name="slowmode",
        description="Set slowmode for a text channel.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("manage_channels",),
        bot_permissions=("manage_channels",),
        options=("seconds", "channel?"),
    ),
    CommandSpec(
        name="level-reset",
        description="Reset a member's XP (text, voice, or all).",
        category="Levels",
        module="leveling",
        default_member_permissions=("manage_guild",),
        options=("member", "metric"),
    ),
    CommandSpec(
        name="invites-top",
        description="Show the invite leaderboard.",
        category="Invites",
        module="invites",
        visibility="public",
    ),
    CommandSpec(
        name="ticket add",
        description="Add a member to this ticket channel.",
        category="Tickets",
        module="tickets",
        bot_permissions=("manage_channels",),
        options=("member",),
    ),
    CommandSpec(
        name="ticket remove",
        description="Remove a member from this ticket channel.",
        category="Tickets",
        module="tickets",
        bot_permissions=("manage_channels",),
        options=("member",),
    ),
    # Phase 3
    CommandSpec(
        name="modlogs",
        description="Show recent moderation actions for this server.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("manage_guild",),
        options=("limit?",),
    ),
    CommandSpec(
        name="verification pending",
        description="Show pending manual verifications (dashboard link).",
        category="Verification",
        default_member_permissions=("manage_roles",),
        options=(),
    ),
    CommandSpec(
        name="Kick",
        description="Kick this member.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("kick_members",),
        bot_permissions=("kick_members",),
        command_type="user",
    ),
    CommandSpec(
        name="Ban",
        description="Ban this user.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("ban_members",),
        bot_permissions=("ban_members",),
        command_type="user",
    ),
    CommandSpec(
        name="Timeout",
        description="Timeout this member for 10 minutes.",
        category="Moderation",
        module="moderation",
        default_member_permissions=("moderate_members",),
        bot_permissions=("moderate_members",),
        command_type="user",
    ),
    CommandSpec(
        name="User info",
        description="Show info about this member.",
        category="Info",
        command_type="user",
    ),
)


def command_by_name(name: str) -> CommandSpec | None:
    lowered = name.strip().lower()
    for spec in COMMANDS:
        if spec.name.lower() == lowered:
            return spec
    return None


def commands_for_help() -> tuple[CommandSpec, ...]:
    """Chat commands only (exclude context menus from /help listings)."""

    return tuple(spec for spec in COMMANDS if spec.command_type == "chat")


def manifest_snapshot() -> dict[str, Any]:
    return {
        "version": COMMAND_MANIFEST_VERSION,
        "commands": [asdict(spec) for spec in COMMANDS],
    }


def permission_bit_names(spec: CommandSpec) -> frozenset[str]:
    return frozenset(spec.default_member_permissions)
