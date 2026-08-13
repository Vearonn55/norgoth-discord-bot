"""Backfill Verification Logs into Discord Logs from legacy purpose=log bindings.

Guilds that configured a Verification Log channel under Member Verification
store it as ``guild_channel_bindings.purpose='log'``. Discord Logs ownership
uses ``logging_channels.key='verification'`` plus event mappings.

This script is opt-in and idempotent. For each guild with a legacy log binding:

1. Ensures an active ``LoggingConfiguration`` exists (creates a minimal one
   when missing so dual-read can graduate to Discord Logs ownership).
2. Upserts ``LoggingChannel(key='verification')`` with the legacy channel ID
   when that key is absent. If a verification channel already exists with a
   different Discord channel ID, the existing Discord Logs value is kept.
3. Upserts enabled mappings for all verification event types.
4. Rewrites the Redis routing snapshot.

It never invents a Discord channel ID.

Usage:
    python -m scripts.backfill_verification_log_mappings
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session_factory
from app.models.enums import GuildChannelPurpose
from app.models.guild import Guild
from app.models.guild_bindings import GuildChannelBinding
from app.models.logging_config import (
    LoggingChannel,
    LoggingConfiguration,
    LoggingEventMapping,
)
from app.routes.logging_config import _write_routing_snapshot
from app.services.logging_events import GROUP_DEFAULT_COLORS

VERIFICATION_EVENTS = (
    "verification_succeeded",
    "verification_succeeded_role_pending",
    "verification_manual_review_required",
    "verification_denied",
    "verification_manual_decision",
)
VERIFICATION_KEY = "verification"
VERIFICATION_COLOR = GROUP_DEFAULT_COLORS.get(VERIFICATION_KEY, 0x34D399)


async def _ensure_config(
    session,
    *,
    discord_guild_id: str,
) -> LoggingConfiguration:
    config = (
        await session.scalars(
            select(LoggingConfiguration)
            .options(
                selectinload(LoggingConfiguration.channels),
                selectinload(LoggingConfiguration.event_mappings),
            )
            .where(LoggingConfiguration.guild_id == discord_guild_id)
        )
    ).first()
    if config is not None:
        return config

    config = LoggingConfiguration(
        guild_id=discord_guild_id,
        enabled=True,
        status="active",
        created_by="backfill_verification_log_mappings",
    )
    session.add(config)
    await session.flush()
    # Re-load with relationships for callers.
    refreshed = (
        await session.scalars(
            select(LoggingConfiguration)
            .options(
                selectinload(LoggingConfiguration.channels),
                selectinload(LoggingConfiguration.event_mappings),
            )
            .where(LoggingConfiguration.id == config.id)
        )
    ).one()
    return refreshed


async def main() -> None:
    factory = get_session_factory()
    created_channels = 0
    created_mappings = 0
    kept_existing = 0
    updated_guilds = 0
    skipped = 0

    async with factory() as session:
        rows = (
            await session.execute(
                select(Guild.discord_guild_id, GuildChannelBinding.channel_id)
                .join(
                    GuildChannelBinding,
                    GuildChannelBinding.guild_id == Guild.id,
                )
                .where(GuildChannelBinding.purpose == GuildChannelPurpose.LOG)
            )
        ).all()

        for discord_guild_id, legacy_channel_id in rows:
            guild_id = str(discord_guild_id)
            channel_id = str(legacy_channel_id).strip()
            if not channel_id:
                skipped += 1
                continue

            config = await _ensure_config(session, discord_guild_id=guild_id)
            by_key = {c.key: c for c in config.channels}
            verification_channel = by_key.get(VERIFICATION_KEY)

            if verification_channel is None:
                verification_channel = LoggingChannel(
                    guild_id=guild_id,
                    key=VERIFICATION_KEY,
                    name="verification-log",
                    channel_id=channel_id,
                    norgoth_managed=False,
                    default_color=VERIFICATION_COLOR,
                    position=len(config.channels),
                    enabled=True,
                )
                config.channels.append(verification_channel)
                created_channels += 1
                print(
                    f"guild {guild_id}: created verification channel → "
                    f"{channel_id}"
                )
            elif not verification_channel.channel_id:
                verification_channel.channel_id = channel_id
                verification_channel.enabled = True
                print(
                    f"guild {guild_id}: filled empty verification channel → "
                    f"{channel_id}"
                )
            elif verification_channel.channel_id != channel_id:
                kept_existing += 1
                print(
                    f"guild {guild_id}: keep Discord Logs "
                    f"{verification_channel.channel_id} "
                    f"(legacy binding {channel_id} ignored)"
                )
            else:
                verification_channel.enabled = True

            await session.flush()

            existing = {m.event_type: m for m in config.event_mappings}
            added: list[str] = []
            for event_type in VERIFICATION_EVENTS:
                mapping = existing.get(event_type)
                if mapping is None:
                    mapping = LoggingEventMapping(
                        guild_id=guild_id,
                        event_type=event_type,
                        color=VERIFICATION_COLOR,
                        enabled=True,
                    )
                    mapping.channel = verification_channel
                    config.event_mappings.append(mapping)
                    created_mappings += 1
                    added.append(event_type)
                else:
                    mapping.enabled = True
                    mapping.logging_channel_id = verification_channel.id
                    mapping.color = mapping.color or VERIFICATION_COLOR

            await session.flush()
            refreshed = (
                await session.scalars(
                    select(LoggingConfiguration)
                    .options(
                        selectinload(LoggingConfiguration.channels),
                        selectinload(LoggingConfiguration.event_mappings),
                    )
                    .where(LoggingConfiguration.id == config.id)
                )
            ).one()
            await _write_routing_snapshot(refreshed)
            updated_guilds += 1
            if added:
                print(f"guild {guild_id}: mappings +{added}")

        if created_channels or created_mappings or updated_guilds:
            await session.commit()

    print(
        f"Done. Guilds touched={updated_guilds}, channels created="
        f"{created_channels}, mappings created={created_mappings}, "
        f"kept existing Discord Logs={kept_existing}, skipped={skipped}."
    )


if __name__ == "__main__":
    asyncio.run(main())
