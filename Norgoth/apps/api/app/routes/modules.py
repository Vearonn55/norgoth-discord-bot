"""Per-guild module master switches (welcome, automod, tickets, ...).

Stored as a JSON object under norgoth:guild:{id}:modules. Every module
defaults to enabled; the bot checks the flag before acting.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_through, save_config

router = APIRouter(
    tags=["Modules"],
    dependencies=[Depends(guild_manager_dependency())],
)

MODULE_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "welcome",
        "name": "Welcome & Leave Messages",
        "description": "Join/leave announcements in the configured channels.",
    },
    {
        "key": "autorole",
        "name": "Auto-Role",
        "description": "Automatically grant a role to new members.",
    },
    {
        "key": "moderation",
        "name": "Moderation Commands",
        "description": "Slash commands: kick, ban, timeout, purge, unban, lock, and more.",
    },
    {
        "key": "automod",
        "name": "Auto-Moderation",
        "description": "Prohibited words, spam, invite links, mass mentions.",
    },
    {
        "key": "logging",
        "name": "Server Logging",
        "description": "Member, message, role, and channel event logs.",
    },
    {
        "key": "tickets",
        "name": "Ticket System",
        "description": "Support ticket panel and private ticket channels.",
    },
    {
        "key": "leveling",
        "name": "Leveling & Activity",
        "description": "XP per message, ranks, and role rewards.",
    },
    {
        "key": "autoresponder",
        "name": "Auto Responses",
        "description": "Keyword-triggered automatic replies.",
    },
    {
        "key": "roles",
        "name": "Self-Assignable Roles",
        "description": "Self-assignable role menus with buttons.",
    },
    {
        "key": "invites",
        "name": "Invite Tracking",
        "description": "Attribute joins to inviters and keep counters.",
    },
    {
        "key": "notifications",
        "name": "Content Notifications",
        "description": "Multi-platform creator alerts via managed Discord webhooks.",
    },
    {
        "key": "raid",
        "name": "Raid Protection",
        "description": "Detect join floods and optionally lock down the server.",
    },
    {
        "key": "honeypot",
        "name": "Honeypot",
        "description": "Trap channels that punish members who post in them.",
    },
    {
        "key": "rich_link_embeds",
        "name": "Link Embeds",
        "description": "Reply with embed-friendly social media link rewrites.",
    },
    {
        "key": "rss_feeds",
        "name": "RSS Feeds",
        "description": "Post new items from RSS 2.0 / Atom feeds into a channel.",
    },
    {
        "key": "feed_channels",
        "name": "Top Trending",
        "description": "Ranked Daily/Weekly/Monthly/All-Time feeds by Net Upvotes.",
    },
    {
        "key": "campaigns",
        "name": "Campaign Messaging",
        "description": "Channel broadcasts and member DM campaigns.",
    },
]

MODULE_KEYS = [module["key"] for module in MODULE_DEFINITIONS]


def modules_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:modules"


class ModulesUpdate(BaseModel):
    modules: dict[str, bool]


async def read_module_flags(redis_client, guild_id: str) -> dict[str, bool]:
    parsed = await read_through(guild_id, "modules", redis_client)

    stored: dict[str, Any] = parsed if isinstance(parsed, dict) else {}

    return {key: bool(stored.get(key, True)) for key in MODULE_KEYS}


@router.get("/guilds/{guild_id}/modules")
async def get_modules(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        flags = await read_module_flags(redis_client, guild_id)
    finally:
        await redis_client.aclose()

    return {
        "guild_id": guild_id,
        "modules": [
            {**definition, "enabled": flags[definition["key"]]}
            for definition in MODULE_DEFINITIONS
        ],
    }


@router.put("/guilds/{guild_id}/modules")
async def update_modules(guild_id: str, payload: ModulesUpdate) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        flags = await read_module_flags(redis_client, guild_id)

        for key, enabled in payload.modules.items():
            if key in flags:
                flags[key] = bool(enabled)

        flags["updated_at"] = now_iso()  # type: ignore[assignment]
        await save_config(guild_id, "modules", flags, enabled=True)
    finally:
        await redis_client.aclose()

    return {
        "guild_id": guild_id,
        "modules": [
            {**definition, "enabled": bool(flags[definition["key"]])}
            for definition in MODULE_DEFINITIONS
        ],
    }
