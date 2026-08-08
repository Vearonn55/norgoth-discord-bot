"""Config-driven logging: CRUD, Discord provisioning, reconcile/repair, health.

Persistence lives in Postgres (logging_configurations + channels + event
mappings). Every mutation also writes a denormalised routing snapshot to Redis
that the bot reads at runtime to route events to channels with colours.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_database_session
from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_CATEGORY,
    CHANNEL_TYPE_TEXT,
    DiscordBotAPIError,
    DiscordBotClient,
)
from app.models.logging_config import (
    LoggingChannel,
    LoggingConfiguration,
    LoggingEventMapping,
)
from app.services.campaign_store import get_redis, now_iso
from app.services.logging_events import (
    GROUP_DEFAULT_COLORS,
    catalog_payload,
    group_for_event,
)

logger = logging.getLogger("norgoth.logging_config")

SNOWFLAKE = r"^[0-9]{5,25}$"

router = APIRouter(
    tags=["Logging"],
    dependencies=[Depends(guild_manager_dependency())],
)


def routing_snapshot_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:logging:routing"


def legacy_logging_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:logging"


def legacy_automation_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:automation"


# Legacy per-category channel field -> (group key, list of event types).
# Widened so guilds upgrading from the legacy Redis logging config keep their
# member ban/unban/timeout, voice, and server coverage (these previously fell
# through to the default log channel).
_LEGACY_GROUP_EVENTS = {
    "member": ("member", [
        "member_join",
        "member_leave",
        "member_ban",
        "member_unban",
        "member_nickname",
        "member_roles_update",
        "member_timeout",
    ]),
    "message": ("message", ["message_edit", "message_delete", "message_bulk_delete"]),
    "role": ("role", ["role_create", "role_delete", "role_update"]),
    "channel": ("channel", ["channel_create", "channel_delete", "channel_update"]),
    "voice": ("voice", ["voice_join", "voice_leave", "voice_move"]),
    "server": ("server", ["guild_update"]),
}


# ── Request bodies ──────────────────────────────────────────────────────────
class LoggingChannelBody(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    norgoth_managed: bool = False
    default_color: Optional[int] = Field(default=None, ge=0, le=0xFFFFFF)
    position: int = 0


class LoggingEventBody(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    channel_key: Optional[str] = Field(default=None, max_length=64)
    color: Optional[int] = Field(default=None, ge=0, le=0xFFFFFF)
    enabled: bool = True


class LoggingConfigBody(BaseModel):
    enabled: bool = True
    category_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    category_name: Optional[str] = Field(default=None, max_length=100)
    norgoth_managed_category: bool = False
    channels: list[LoggingChannelBody] = Field(default_factory=list, max_length=25)
    events: list[LoggingEventBody] = Field(default_factory=list, max_length=200)


class LoggingStateBody(BaseModel):
    """Runtime state mutation only — never touches channels/events."""

    enabled: bool


# ── Serialisation ────────────────────────────────────────────────────────────
def _serialize(config: LoggingConfiguration) -> dict[str, Any]:
    channels_by_id = {channel.id: channel for channel in config.channels}
    return {
        "id": str(config.id),
        "guild_id": config.guild_id,
        "enabled": config.enabled,
        "status": config.status,
        "category_id": config.category_id,
        "category_name": config.category_name,
        "norgoth_managed_category": config.norgoth_managed_category,
        "channels": [
            {
                "id": str(channel.id),
                "key": channel.key,
                "name": channel.name,
                "channel_id": channel.channel_id,
                "norgoth_managed": channel.norgoth_managed,
                "default_color": channel.default_color,
                "position": channel.position,
            }
            for channel in sorted(config.channels, key=lambda c: c.position)
        ],
        "events": [
            {
                "event_type": mapping.event_type,
                "channel_key": (
                    channels_by_id[mapping.logging_channel_id].key
                    if mapping.logging_channel_id in channels_by_id
                    else None
                ),
                "color": mapping.color,
                "enabled": mapping.enabled,
            }
            for mapping in config.event_mappings
        ],
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


async def _load(
    session: AsyncSession,
    guild_id: str,
    *,
    for_update: bool = False,
) -> LoggingConfiguration | None:
    stmt = (
        select(LoggingConfiguration)
        .where(LoggingConfiguration.guild_id == guild_id)
        .options(
            selectinload(LoggingConfiguration.channels),
            selectinload(LoggingConfiguration.event_mappings),
        )
    )
    if for_update:
        # Serialize concurrent writers (e.g. rapid enable/disable toggling) so
        # they cannot interleave delete/insert cycles and duplicate rows.
        stmt = stmt.with_for_update(of=LoggingConfiguration)
    return await session.scalar(stmt)


def _effective_color(
    mapping: LoggingEventMapping,
    channel: LoggingChannel | None,
) -> int | None:
    if mapping.color is not None:
        return mapping.color
    if channel and channel.default_color is not None:
        return channel.default_color
    group = group_for_event(mapping.event_type)
    if group:
        return GROUP_DEFAULT_COLORS.get(group)
    return None


async def _write_routing_snapshot(config: LoggingConfiguration) -> None:
    """Denormalise the config into a compact event -> channel/colour map."""

    channels_by_id = {channel.id: channel for channel in config.channels}
    events: dict[str, Any] = {}
    for mapping in config.event_mappings:
        if not mapping.enabled:
            continue
        channel = channels_by_id.get(mapping.logging_channel_id)
        if not channel or not channel.channel_id:
            continue
        events[mapping.event_type] = {
            "channel_id": channel.channel_id,
            "color": _effective_color(mapping, channel),
        }

    snapshot = {
        "enabled": config.enabled and config.status == "active",
        "category_id": config.category_id,
        "events": events,
        "updated_at": now_iso(),
    }

    redis_client = await get_redis()
    try:
        await redis_client.set(
            routing_snapshot_key(config.guild_id), json.dumps(snapshot)
        )
    finally:
        await redis_client.aclose()


async def _clear_routing_snapshot(guild_id: str) -> None:
    redis_client = await get_redis()
    try:
        await redis_client.delete(routing_snapshot_key(guild_id))
    finally:
        await redis_client.aclose()


async def _read_legacy(guild_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the legacy Redis logging + automation configs for a guild."""

    redis_client = await get_redis()
    try:
        raw_logging = await redis_client.get(legacy_logging_key(guild_id))
        raw_automation = await redis_client.get(legacy_automation_key(guild_id))
    finally:
        await redis_client.aclose()

    def _decode(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    return _decode(raw_logging), _decode(raw_automation)


async def _import_legacy_config(
    session: AsyncSession, guild_id: str
) -> LoggingConfiguration | None:
    """Build a Postgres draft from legacy Redis settings so nothing is lost.

    Only existing channels are referenced (nothing is provisioned). When the
    import yields at least one usable channel it is stored as an active config
    and a routing snapshot is written so logging keeps working seamlessly.
    """

    legacy_logging, legacy_automation = await _read_legacy(guild_id)
    if not legacy_logging and not legacy_automation:
        return None

    default_channel = legacy_logging.get("log_channel_id")
    mod_channel = legacy_automation.get("mod_log_channel_id")

    # Resolve one channel per group from per-category or default channel.
    group_channels: dict[str, str] = {}
    for field, (group_key, _events) in _LEGACY_GROUP_EVENTS.items():
        if not legacy_logging.get(f"{field}_events", True):
            continue
        channel_id = legacy_logging.get(f"{field}_channel_id") or default_channel
        if channel_id:
            group_channels[group_key] = str(channel_id)

    if mod_channel:
        group_channels["moderation"] = str(mod_channel)

    if not group_channels:
        return None

    config = LoggingConfiguration(
        guild_id=guild_id,
        enabled=bool(legacy_logging.get("enabled", True)),
        status="active",  # references existing channels; nothing to provision
        norgoth_managed_category=False,
    )
    session.add(config)
    await session.flush()

    channels_by_key: dict[str, LoggingChannel] = {}
    position = 0
    for group_key, channel_id in group_channels.items():
        channel = LoggingChannel(
            logging_configuration_id=config.id,
            guild_id=guild_id,
            key=group_key,
            name=f"{group_key}-log",
            channel_id=channel_id,
            norgoth_managed=False,
            default_color=GROUP_DEFAULT_COLORS.get(group_key),
            position=position,
        )
        session.add(channel)
        channels_by_key[group_key] = channel
        position += 1
    await session.flush()

    # Map every event in an imported group to that group's channel.
    imported_groups = {
        group_key: events for _f, (group_key, events) in _LEGACY_GROUP_EVENTS.items()
    }
    imported_groups["moderation"] = ["mod_kick", "mod_ban", "mod_timeout", "mod_purge", "mod_warn"]

    for group_key, events in imported_groups.items():
        channel = channels_by_key.get(group_key)
        if channel is None:
            continue
        for event_type in events:
            session.add(
                LoggingEventMapping(
                    logging_configuration_id=config.id,
                    guild_id=guild_id,
                    event_type=event_type,
                    logging_channel_id=channel.id,
                    color=None,
                    enabled=True,
                )
            )

    await session.commit()
    imported = await _load(session, guild_id)
    if imported is not None:
        await _write_routing_snapshot(imported)
    return imported


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/guilds/{guild_id}/logging/event-types")
async def get_event_types(
    guild_id: str = Path(pattern=SNOWFLAKE),
) -> dict[str, Any]:
    return catalog_payload()


@router.get("/guilds/{guild_id}/logging/config")
async def get_logging_config(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    config = await _load(session, guild_id)
    if config is None:
        # No Postgres config yet — attempt a one-time import of legacy Redis
        # settings so upgrading guilds don't lose their logging configuration.
        config = await _import_legacy_config(session, guild_id)
    if config is None:
        return {"guild_id": guild_id, "config": None}
    return {"guild_id": guild_id, "config": _serialize(config)}


@router.patch("/guilds/{guild_id}/logging/config")
async def set_logging_state(
    body: LoggingStateBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Idempotent runtime-state toggle.

    Only flips ``enabled`` on the existing configuration; it never recreates or
    provisions channels/events. Repeated or concurrent calls converge to the
    requested state (the config row is locked for the update).
    """

    config = await _load(session, guild_id, for_update=True)
    if config is None:
        raise HTTPException(status_code=404, detail="No logging configuration.")

    config.enabled = body.enabled
    await session.commit()
    config = await _load(session, guild_id)
    assert config is not None
    await _write_routing_snapshot(config)
    return {"guild_id": guild_id, "config": _serialize(config)}


@router.put("/guilds/{guild_id}/logging/config")
async def upsert_logging_config(
    body: LoggingConfigBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    # Lock the config row so concurrent writers serialize instead of racing
    # delete/insert cycles (previously a source of duplicate rows + crashes).
    config = await _load(session, guild_id, for_update=True)
    if config is None:
        config = LoggingConfiguration(guild_id=guild_id, status="draft")
        session.add(config)
        await session.flush()
        # Reload with relationships eagerly populated: async sessions cannot
        # lazy-load `channels`/`event_mappings` on attribute access below.
        config = await _load(session, guild_id, for_update=True)
        assert config is not None

    config.enabled = body.enabled
    config.category_id = body.category_id
    config.category_name = body.category_name
    config.norgoth_managed_category = body.norgoth_managed_category

    # Reconcile channels by their stable `key` (update-in-place, insert new,
    # delete only removed) rather than delete-all-then-recreate. This keeps
    # row identity stable, avoids StaleDataError under concurrency, and — with
    # the (config_id, key) unique constraint — prevents duplicate rows.
    existing_channels: dict[str, LoggingChannel] = {}
    for channel in list(config.channels):
        # Guard against any pre-existing duplicates: keep the first, drop rest.
        if channel.key in existing_channels:
            await session.delete(channel)
        else:
            existing_channels[channel.key] = channel

    body_keys = {channel_body.key for channel_body in body.channels}
    for key, channel in list(existing_channels.items()):
        if key not in body_keys:
            await session.delete(channel)
            del existing_channels[key]

    channels_by_key: dict[str, LoggingChannel] = {}
    for channel_body in body.channels:
        channel = existing_channels.get(channel_body.key)
        if channel is None:
            channel = LoggingChannel(guild_id=guild_id, key=channel_body.key)
            config.channels.append(channel)
        channel.name = channel_body.name
        channel.channel_id = channel_body.channel_id
        channel.norgoth_managed = channel_body.norgoth_managed
        channel.default_color = channel_body.default_color
        channel.position = channel_body.position
        channels_by_key[channel_body.key] = channel
    await session.flush()

    # Reconcile event mappings by `event_type` (one mapping per type per config).
    existing_events: dict[str, LoggingEventMapping] = {}
    for mapping in list(config.event_mappings):
        if mapping.event_type in existing_events:
            await session.delete(mapping)
        else:
            existing_events[mapping.event_type] = mapping

    body_event_types = {event_body.event_type for event_body in body.events}
    for event_type, mapping in list(existing_events.items()):
        if event_type not in body_event_types:
            await session.delete(mapping)
            del existing_events[event_type]

    for event_body in body.events:
        channel = channels_by_key.get(event_body.channel_key or "")
        mapping = existing_events.get(event_body.event_type)
        if mapping is None:
            mapping = LoggingEventMapping(
                guild_id=guild_id, event_type=event_body.event_type
            )
            config.event_mappings.append(mapping)
        mapping.color = event_body.color
        mapping.enabled = event_body.enabled
        mapping.channel = channel

    await session.commit()
    config = await _load(session, guild_id)
    assert config is not None
    await _write_routing_snapshot(config)
    return {"guild_id": guild_id, "config": _serialize(config)}


@router.post("/guilds/{guild_id}/logging/provision")
async def provision_logging(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Create the Discord category + channels for Norgoth-managed entries."""

    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    config = await _load(session, guild_id)
    if config is None:
        raise HTTPException(status_code=404, detail="No logging configuration.")

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)

        try:
            if config.norgoth_managed_category and not config.category_id:
                created = await bot.create_guild_channel(
                    guild_id,
                    name=config.category_name or "Norgoth Logs",
                    channel_type=CHANNEL_TYPE_CATEGORY,
                    reason="Norgoth logging setup",
                )
                config.category_id = str(created.get("id") or "") or None
                results.append({"type": "category", "status": "created"})
        except DiscordBotAPIError as error:
            await session.commit()
            raise HTTPException(
                status_code=502,
                detail=f"Could not create the logging category: {error}",
            ) from error

        for channel in sorted(config.channels, key=lambda c: c.position):
            if not channel.norgoth_managed or channel.channel_id:
                continue
            try:
                created = await bot.create_guild_channel(
                    guild_id,
                    name=channel.name,
                    channel_type=CHANNEL_TYPE_TEXT,
                    parent_id=config.category_id,
                    reason="Norgoth logging setup",
                )
                channel.channel_id = str(created.get("id") or "") or None
                results.append(
                    {"type": "channel", "key": channel.key, "status": "created"}
                )
            except DiscordBotAPIError as error:
                # Persist what we have; report the failure without aborting.
                results.append(
                    {
                        "type": "channel",
                        "key": channel.key,
                        "status": "error",
                        "error": str(error),
                    }
                )

    if all(result.get("status") != "error" for result in results):
        config.status = "active"

    await session.commit()
    config = await _load(session, guild_id)
    assert config is not None
    await _write_routing_snapshot(config)
    return {"guild_id": guild_id, "config": _serialize(config), "results": results}


async def _channel_health(
    bot: DiscordBotClient,
    channel: LoggingChannel,
) -> dict[str, Any]:
    if not channel.channel_id:
        return {"key": channel.key, "status": "unprovisioned"}
    try:
        await bot.get_channel(channel.channel_id)
        return {"key": channel.key, "status": "ok", "channel_id": channel.channel_id}
    except DiscordBotAPIError as error:
        status = "missing" if error.status_code == 404 else "error"
        return {
            "key": channel.key,
            "status": status,
            "channel_id": channel.channel_id,
            "error": str(error),
        }


@router.get("/guilds/{guild_id}/logging/health")
@router.post("/guilds/{guild_id}/logging/reconcile")
async def reconcile_logging(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    config = await _load(session, guild_id)
    if config is None:
        raise HTTPException(status_code=404, detail="No logging configuration.")

    channel_health: list[dict[str, Any]] = []
    category_status = "n/a"

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)

        if config.category_id:
            try:
                await bot.get_channel(config.category_id)
                category_status = "ok"
            except DiscordBotAPIError as error:
                category_status = "missing" if error.status_code == 404 else "error"

        for channel in sorted(config.channels, key=lambda c: c.position):
            channel_health.append(await _channel_health(bot, channel))

    healthy = category_status in ("ok", "n/a") and all(
        item["status"] in ("ok", "unprovisioned") for item in channel_health
    )

    return {
        "guild_id": guild_id,
        "healthy": healthy,
        "category_status": category_status,
        "channels": channel_health,
    }


@router.post("/guilds/{guild_id}/logging/repair")
async def repair_logging(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Recreate Norgoth-managed channels that are missing in Discord."""

    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    config = await _load(session, guild_id)
    if config is None:
        raise HTTPException(status_code=404, detail="No logging configuration.")

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)

        # Recreate the category first if it went missing.
        if config.norgoth_managed_category and config.category_id:
            try:
                await bot.get_channel(config.category_id)
            except DiscordBotAPIError as error:
                if error.status_code == 404:
                    try:
                        created = await bot.create_guild_channel(
                            guild_id,
                            name=config.category_name or "Norgoth Logs",
                            channel_type=CHANNEL_TYPE_CATEGORY,
                            reason="Norgoth logging repair",
                        )
                        config.category_id = str(created.get("id") or "") or None
                        results.append({"type": "category", "status": "recreated"})
                    except DiscordBotAPIError as create_error:
                        results.append(
                            {
                                "type": "category",
                                "status": "error",
                                "error": str(create_error),
                            }
                        )

        for channel in sorted(config.channels, key=lambda c: c.position):
            if not channel.norgoth_managed:
                continue
            needs_recreate = not channel.channel_id
            if channel.channel_id:
                try:
                    await bot.get_channel(channel.channel_id)
                except DiscordBotAPIError as error:
                    needs_recreate = error.status_code == 404
            if not needs_recreate:
                continue
            try:
                created = await bot.create_guild_channel(
                    guild_id,
                    name=channel.name,
                    channel_type=CHANNEL_TYPE_TEXT,
                    parent_id=config.category_id,
                    reason="Norgoth logging repair",
                )
                channel.channel_id = str(created.get("id") or "") or None
                results.append(
                    {"type": "channel", "key": channel.key, "status": "recreated"}
                )
            except DiscordBotAPIError as error:
                results.append(
                    {
                        "type": "channel",
                        "key": channel.key,
                        "status": "error",
                        "error": str(error),
                    }
                )

    await session.commit()
    config = await _load(session, guild_id)
    assert config is not None
    await _write_routing_snapshot(config)
    return {"guild_id": guild_id, "config": _serialize(config), "results": results}


@router.get("/guilds/{guild_id}/logging/permissions")
async def logging_permissions(
    guild_id: str = Path(pattern=SNOWFLAKE),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        try:
            await bot.get_guild(guild_id)
            bot_in_guild = True
        except DiscordBotAPIError as error:
            if error.status_code in (403, 404):
                bot_in_guild = False
            else:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not verify bot permissions: {error}",
                ) from error

    return {
        "guild_id": guild_id,
        "bot_in_guild": bot_in_guild,
        "required_permissions": ["Manage Channels", "View Channels", "Send Messages"],
    }


@router.delete("/guilds/{guild_id}/logging/config")
async def reset_logging_config(
    delete_discord_resources: bool = False,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Delete the configuration. Optionally delete Norgoth-managed channels."""

    config = await _load(session, guild_id)
    if config is None:
        return {"ok": True, "deleted": False}

    discord_deleted = 0
    discord_failed = 0

    if delete_discord_resources:
        settings = get_settings()
        if not settings.discord_bot_token:
            raise HTTPException(
                status_code=503, detail="Discord bot token not configured."
            )
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            for channel in config.channels:
                if channel.norgoth_managed and channel.channel_id:
                    try:
                        await bot.delete_channel(
                            channel.channel_id, reason="Norgoth logging reset"
                        )
                        discord_deleted += 1
                    except DiscordBotAPIError:
                        discord_failed += 1
            if config.norgoth_managed_category and config.category_id:
                try:
                    await bot.delete_channel(
                        config.category_id, reason="Norgoth logging reset"
                    )
                    discord_deleted += 1
                except DiscordBotAPIError:
                    discord_failed += 1

    await session.delete(config)
    await session.commit()
    await _clear_routing_snapshot(guild_id)

    return {
        "ok": True,
        "deleted": True,
        "discord_deleted": discord_deleted,
        "discord_failed": discord_failed,
    }
