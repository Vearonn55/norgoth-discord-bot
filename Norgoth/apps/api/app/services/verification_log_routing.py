"""Resolve the Discord channel for Member Verification log embeds.

Ownership of verification log delivery belongs to Discord Logs
(``logging_channels.key='verification'`` + event mappings). Legacy guilds may
still have a ``guild_channel_bindings.purpose='log'`` channel; this module
dual-reads so rolling deployments do not drop log delivery.

PostgreSQL is authoritative. The Redis routing snapshot is an optional
acceleration that mirrors the bot's read path.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session_factory
from app.models.logging_config import LoggingConfiguration
from app.routes.logging_config import routing_snapshot_key
from app.services.campaign_store import get_redis

logger = logging.getLogger(__name__)

VerificationLogEvent = Literal[
    "verification_succeeded",
    "verification_succeeded_role_pending",
    "verification_manual_review_required",
    "verification_denied",
    "verification_manual_decision",
]

VERIFICATION_GROUP_KEY = "verification"


def classification_to_event_type(
    *,
    allowed: bool,
    manual_review: bool,
    role_grant_failed: bool,
) -> VerificationLogEvent:
    """Map OAuth verification outcome to a Discord Logs event type."""

    if allowed and not role_grant_failed:
        return "verification_succeeded"
    if allowed and role_grant_failed:
        return "verification_succeeded_role_pending"
    if manual_review:
        return "verification_manual_review_required"
    return "verification_denied"


async def resolve_verification_log_channel(
    *,
    discord_guild_id: str,
    event_type: str,
    legacy_log_channel_id: str | None = None,
) -> tuple[str | None, Literal["logging", "legacy_binding", "none"]]:
    """Return ``(channel_id, source)`` for a verification log event.

    Prefer an enabled Discord Logs mapping for ``event_type``. Fall back to the
    legacy Member Verification log binding when no logging route exists.
    Never returns two channels — callers must deliver at most once.
    """

    guild_id = str(discord_guild_id)
    routed = await _resolve_from_logging(guild_id, event_type)
    if routed:
        return routed, "logging"

    legacy = (legacy_log_channel_id or "").strip()
    if legacy:
        logger.info(
            "verification_log_routing source=legacy_binding guild_id=%s "
            "event_type=%s channel_id=%s",
            guild_id,
            event_type,
            legacy,
        )
        return legacy, "legacy_binding"

    return None, "none"


async def _resolve_from_logging(guild_id: str, event_type: str) -> str | None:
    """Try Redis snapshot first, then PostgreSQL."""

    from_snapshot = await _resolve_from_snapshot(guild_id, event_type)
    if from_snapshot is not None:
        return from_snapshot
    return await _resolve_from_postgres(guild_id, event_type)


async def _resolve_from_snapshot(guild_id: str, event_type: str) -> str | None:
    try:
        redis_client = await get_redis()
        try:
            raw = await redis_client.get(routing_snapshot_key(guild_id))
        finally:
            await redis_client.aclose()
    except Exception:
        logger.exception(
            "verification_log_routing snapshot_read_failed guild_id=%s",
            guild_id,
        )
        return None

    if not raw:
        return None

    try:
        snapshot = json.loads(raw)
    except (TypeError, ValueError):
        return None

    if not snapshot.get("enabled"):
        return None

    events = snapshot.get("events") or {}
    entry = events.get(event_type)
    if not isinstance(entry, dict):
        return None
    channel_id = str(entry.get("channel_id") or "").strip()
    return channel_id or None


async def _resolve_from_postgres(guild_id: str, event_type: str) -> str | None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            config = (
                await session.scalars(
                    select(LoggingConfiguration)
                    .options(
                        selectinload(LoggingConfiguration.channels),
                        selectinload(LoggingConfiguration.event_mappings),
                    )
                    .where(
                        LoggingConfiguration.guild_id == guild_id,
                        LoggingConfiguration.status == "active",
                    )
                )
            ).first()
    except Exception:
        logger.exception(
            "verification_log_routing postgres_read_failed guild_id=%s",
            guild_id,
        )
        return None

    if config is None or not config.enabled:
        return None

    channels_by_id = {channel.id: channel for channel in config.channels}
    for mapping in config.event_mappings:
        if mapping.event_type != event_type or not mapping.enabled:
            continue
        channel = channels_by_id.get(mapping.logging_channel_id)
        if (
            channel is None
            or not channel.channel_id
            or not bool(getattr(channel, "enabled", True))
        ):
            continue
        return str(channel.channel_id)

    return None
