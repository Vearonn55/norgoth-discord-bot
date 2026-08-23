"""Bot runtime health and Discord guild resources, backed by bot heartbeats."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.v1.dependencies import DiscordBotClientDependency
from app.api.v1.dependencies_auth import guild_manager_dependency
from app.api.v1.discord_http import http_detail
from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_ANNOUNCEMENT,
    CHANNEL_TYPE_CATEGORY,
    CHANNEL_TYPE_TEXT,
    DiscordBotAPIError,
)
from app.services.campaign_store import get_redis
from app.services.guild_member_snapshot import (
    filter_members,
    merge_include_members,
    paginate_members,
    parse_include_member_ids,
    sort_members_deterministic,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Bot"])

BOT_HEARTBEAT_KEY = "norgoth:bot:heartbeat"
BOT_STATUS_KEY = "norgoth:bot:status"
TEXT_CHANNEL_TYPES = {CHANNEL_TYPE_TEXT, CHANNEL_TYPE_ANNOUNCEMENT}
RESOURCES_REFRESH_LOCK_TTL = 20
RESOURCES_REFRESH_COOLDOWN_TTL = 5
RESOURCES_REFRESH_WAIT_SECONDS = 2.0


def guild_resources_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:resources"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


def guild_resources_refresh_lock_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:resources:refresh-lock"


def guild_resources_refresh_cooldown_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:resources:refresh-cooldown"


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
        if int(channel.get("type", -1)) == CHANNEL_TYPE_CATEGORY and channel.get("id")
    ]
    category_by_id = {item["id"]: item["name"] for item in categories if item["name"]}

    text_channels = []
    for channel in channels:
        if int(channel.get("type", -1)) not in TEXT_CHANNEL_TYPES:
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
                "color": (f"#{color_int:06x}" if color_int > 0 else None),
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


def build_bot_health_payload(
    heartbeat: Any, status: dict[str, Any] | None
) -> dict[str, Any]:
    """Liveness-only health: never include guild inventory (public endpoint)."""

    connected_flag = bool(status and status.get("connected"))
    connected = bool(heartbeat) and connected_flag
    return {
        "connected": connected,
        "stale": connected_flag and not bool(heartbeat),
        "heartbeat_at": heartbeat,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def annotate_resources(
    resources: dict[str, Any],
    *,
    source: str,
    refreshed: bool,
) -> dict[str, Any]:
    payload = dict(resources)
    payload["source"] = source
    payload["refreshed"] = refreshed
    return payload


def raise_discord_resource_error(error: DiscordBotAPIError) -> None:
    status_code = error.status_code or 0
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
            headers={"Retry-After": "5"},
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


async def live_fill_guild_resources(
    *,
    guild_id: str,
    bot_client: Any,
    request_id: str,
) -> dict[str, Any]:
    if bot_client is None:
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

    logger.info(
        "guild_resources_live_fetch request_id=%s guild_id=%s",
        request_id,
        guild_id,
    )
    try:
        guild_payload = await bot_client.get_guild(guild_id)
        channels = await bot_client.list_guild_channels(guild_id)
        roles = await bot_client.list_guild_roles(guild_id)
    except DiscordBotAPIError as error:
        logger.warning(
            "guild_resources_live_fetch_failed request_id=%s guild_id=%s discord_status=%s",
            request_id,
            guild_id,
            error.status_code or 0,
        )
        raise_discord_resource_error(error)

    return _serialize_live_resources(
        guild_id=guild_id,
        guild_payload=guild_payload,
        channels=channels,
        roles=roles,
    )


async def store_guild_resources(redis_client: Any, guild_id: str, resources: dict[str, Any]) -> None:
    await redis_client.set(
        guild_resources_key(guild_id),
        json.dumps(resources, separators=(",", ":")),
    )


@router.get("/bot/health")
async def get_bot_health() -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        heartbeat = await redis_client.get(BOT_HEARTBEAT_KEY)
        status = parse_json(await redis_client.get(BOT_STATUS_KEY))
    finally:
        await redis_client.aclose()

    return build_bot_health_payload(heartbeat, status)


@router.get(
    "/guilds/{guild_id}/discord-resources",
    dependencies=[Depends(guild_manager_dependency())],
)
async def get_guild_discord_resources(
    request: Request,
    guild_id: str,
    bot_client: DiscordBotClientDependency,
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    redis_client = await get_redis()
    request_id = getattr(request.state, "request_id", "unavailable")
    try:
        cached = parse_json(await redis_client.get(guild_resources_key(guild_id)))
        if not refresh:
            if cached is not None:
                return annotate_resources(cached, source="cache", refreshed=False)
            resources = await live_fill_guild_resources(
                guild_id=guild_id,
                bot_client=bot_client,
                request_id=str(request_id),
            )
            await store_guild_resources(redis_client, guild_id, resources)
            return annotate_resources(resources, source="fresh", refreshed=True)

        cooldown_key = guild_resources_refresh_cooldown_key(guild_id)
        if await redis_client.get(cooldown_key):
            if cached is not None:
                return annotate_resources(cached, source="cache", refreshed=False)

        lock_key = guild_resources_refresh_lock_key(guild_id)
        acquired = await redis_client.set(
            lock_key, "1", nx=True, ex=RESOURCES_REFRESH_LOCK_TTL
        )
        if not acquired:
            waited = 0.0
            while waited < RESOURCES_REFRESH_WAIT_SECONDS:
                await asyncio.sleep(0.1)
                waited += 0.1
                cached = parse_json(
                    await redis_client.get(guild_resources_key(guild_id))
                )
                if cached is not None:
                    return annotate_resources(cached, source="cache", refreshed=False)
            if cached is not None:
                return annotate_resources(cached, source="cache", refreshed=False)
            raise HTTPException(
                status_code=503,
                detail=http_detail(
                    "guild_resources_unavailable",
                    "Guild resources are being refreshed. Please retry shortly.",
                ),
            )

        try:
            resources = await live_fill_guild_resources(
                guild_id=guild_id,
                bot_client=bot_client,
                request_id=str(request_id),
            )
            await store_guild_resources(redis_client, guild_id, resources)
            await redis_client.set(
                cooldown_key, "1", ex=RESOURCES_REFRESH_COOLDOWN_TTL
            )
            return annotate_resources(resources, source="fresh", refreshed=True)
        finally:
            if acquired:
                await redis_client.delete(lock_key)
    finally:
        await redis_client.aclose()


@router.get(
    "/guilds/{guild_id}/members",
    dependencies=[Depends(guild_manager_dependency())],
)
async def get_guild_members(
    guild_id: str,
    offset: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=100),
    q: str | None = Query(default=None, max_length=100),
    exclude_bots: bool = Query(default=True),
    include_member_ids: str | None = Query(default=None, max_length=2500),
    exempt_only: bool = Query(default=False),
) -> dict[str, Any]:
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

    if offset is None and limit is None:
        return snapshot

    members_raw = snapshot.get("members")
    if not isinstance(members_raw, list):
        members_raw = []

    members = [
        member for member in members_raw if isinstance(member, dict)
    ]
    sorted_members = sort_members_deterministic(members)
    include_ids = parse_include_member_ids(include_member_ids)
    only_ids = set(include_ids) if exempt_only and include_ids else None
    filtered = filter_members(
        sorted_members,
        q=q,
        exclude_bots=exclude_bots,
        only_member_ids=only_ids,
    )
    page_offset = offset or 0
    page_limit = limit or 10
    page_members, pagination = paginate_members(
        filtered,
        offset=page_offset,
        limit=page_limit,
    )
    included_members = merge_include_members([], sorted_members, include_ids)

    return {
        "guild_id": snapshot.get("guild_id", guild_id),
        "guild_name": snapshot.get("guild_name"),
        "updated_at": snapshot.get("updated_at"),
        "members": page_members,
        "included_members": included_members,
        "pagination": pagination,
    }
