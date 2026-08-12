"""Bot runtime health and Discord guild resources, backed by bot heartbeats."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.dependencies import DiscordBotClientDependency
from app.api.v1.dependencies_auth import guild_manager_dependency
from app.api.v1.discord_http import http_detail
from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.services.campaign_store import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Bot"])

BOT_HEARTBEAT_KEY = "norgoth:bot:heartbeat"
BOT_STATUS_KEY = "norgoth:bot:status"


def guild_resources_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:resources"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


def parse_json(raw: str | bytes | None) -> dict[str, Any] | None:
    if not raw:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _serialize_live_resources(
    *,
    guild_id: str,
    guild_payload: dict[str, Any],
    channels: list[dict[str, Any]],
    roles: list[dict[str, Any]],
) -> dict[str, Any]:
    categories = [
        {"id": str(channel["id"]), "name": str(channel.get("name") or "")}
        for channel in channels
        if int(channel.get("type", -1)) == 4 and channel.get("id")
    ]
    category_by_id = {item["id"]: item["name"] for item in categories if item["name"]}

    text_channels = []
    for channel in channels:
        if int(channel.get("type", -1)) != 0:
            continue
        channel_id = channel.get("id")
        if not channel_id:
            continue
        parent_id = channel.get("parent_id")
        parent_name = category_by_id.get(str(parent_id)) if parent_id else None
        text_channels.append(
            {
                "id": str(channel_id),
                "name": str(channel.get("name") or channel_id),
                "type": "text",
                "category": parent_name,
            }
        )

    normalized_roles = []
    for role in roles:
        role_id = role.get("id")
        if not role_id or str(role_id) == str(guild_id):
            continue
        color_raw = role.get("color")
        try:
            color_int = int(color_raw or 0)
        except (TypeError, ValueError):
            color_int = 0
        position_raw = role.get("position")
        try:
            position = int(position_raw or 0)
        except (TypeError, ValueError):
            position = 0

        normalized_roles.append(
            {
                "id": str(role_id),
                "name": str(role.get("name") or role_id),
                "position": position,
                "managed": bool(role.get("managed")),
                "color": f"#{color_int:06x}",
            }
        )

    normalized_roles.sort(key=lambda item: -int(item.get("position", 0)))

    emojis = []
    for emoji in guild_payload.get("emojis") or []:
        if not isinstance(emoji, dict) or not emoji.get("id"):
            continue
        emojis.append(
            {
                "id": str(emoji["id"]),
                "name": str(emoji.get("name") or emoji["id"]),
                "animated": bool(emoji.get("animated")),
            }
        )

    return {
        "guild_id": str(guild_id),
        "guild_name": str(guild_payload.get("name") or guild_id),
        "member_count": guild_payload.get("approximate_member_count"),
        "channels": text_channels,
        "categories": categories,
        "roles": normalized_roles,
        "emojis": emojis,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/bot/health")
async def get_bot_health() -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        heartbeat = await redis_client.get(BOT_HEARTBEAT_KEY)
        status = parse_json(await redis_client.get(BOT_STATUS_KEY))
    finally:
        await redis_client.aclose()

    connected = bool(heartbeat) and bool(status and status.get("connected"))

    return {
        "connected": connected,
        "heartbeat_at": heartbeat,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": status or {},
    }


@router.get(
    "/guilds/{guild_id}/discord-resources",
    dependencies=[Depends(guild_manager_dependency())],
)
async def get_guild_discord_resources(
    request: Request,
    guild_id: str,
    bot_client: DiscordBotClientDependency,
) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        resources = parse_json(await redis_client.get(guild_resources_key(guild_id)))
    finally:
        await redis_client.aclose()

    if resources is not None:
        return resources

    if bot_client is None:
        # Prefer an actionable ops signal when the bot is alive but the API
        # cannot live-fill because DISCORD_BOT_TOKEN is missing.
        redis_client = await get_redis()
        try:
            heartbeat = await redis_client.get(BOT_HEARTBEAT_KEY)
        finally:
            await redis_client.aclose()
        if heartbeat:
            raise HTTPException(
                status_code=503,
                detail=http_detail(
                    "guild_resources_unavailable",
                    "Guild resources are not cached yet and the API cannot refresh them live. Check that DISCORD_BOT_TOKEN is set for the API service.",
                ),
            )
        raise HTTPException(
            status_code=404,
            detail=http_detail(
                "guild_resources_unavailable",
                "Guild resources are not cached yet. Make sure the bot is online and invited to this server.",
            ),
        )

    request_id = getattr(request.state, "request_id", "unavailable")
    logger.info(
        "guild_resources_cache_miss request_id=%s guild_id=%s",
        request_id,
        guild_id,
    )

    try:
        guild_payload = await bot_client.get_guild(guild_id)
        channels = await bot_client.list_guild_channels(guild_id)
        roles = await bot_client.list_guild_roles(guild_id)
    except DiscordBotAPIError as error:
        status_code = error.status_code or 0
        logger.warning(
            "guild_resources_live_fetch_failed request_id=%s guild_id=%s discord_status=%s",
            request_id,
            guild_id,
            status_code,
        )
        if status_code in {401, 403}:
            raise HTTPException(
                status_code=503,
                detail=http_detail(
                    "missing_bot_permissions",
                    "The bot cannot read channels or roles for this server.",
                ),
            ) from error
        if status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=http_detail(
                    "bot_not_installed",
                    "NorBot is not currently installed in this server.",
                ),
            ) from error
        if status_code == 429:
            raise HTTPException(
                status_code=429,
                detail=http_detail(
                    "discord_rate_limited",
                    "Discord is rate-limiting resource requests. Please retry shortly.",
                ),
            ) from error
        raise HTTPException(
            status_code=503,
            detail=http_detail(
                "discord_temporarily_unavailable",
                "Discord resources are temporarily unavailable. Please retry.",
            ),
        ) from error

    resources = _serialize_live_resources(
        guild_id=guild_id,
        guild_payload=guild_payload,
        channels=channels,
        roles=roles,
    )

    redis_client = await get_redis()
    try:
        await redis_client.set(
            guild_resources_key(guild_id),
            json.dumps(resources, separators=(",", ":")),
        )
    finally:
        await redis_client.aclose()

    return resources


@router.get(
    "/guilds/{guild_id}/members",
    dependencies=[Depends(guild_manager_dependency())],
)
async def get_guild_members(guild_id: str) -> dict[str, Any]:
    """Member snapshot published by the bot (used for DM campaign targeting)."""

    redis_client = await get_redis()

    try:
        snapshot = parse_json(await redis_client.get(guild_members_key(guild_id)))
    finally:
        await redis_client.aclose()

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No member snapshot found for this guild. "
                "Make sure the bot is running with the members intent enabled."
            ),
        )

    return snapshot
