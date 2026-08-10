"""Backfill ticket_opened / ticket_closed logging event mappings.

Guilds whose Logging Configuration was saved before the Tickets group was
added to the catalog have no ``ticket_opened`` / ``ticket_closed`` mappings,
so the bot's routing snapshot silently drops those events.

This script is opt-in and idempotent. For each active logging configuration
that is missing either ticket mapping it:

1. Picks an existing provisioned channel (prefer ``moderation``, else the
   first channel with a real Discord ``channel_id``).
2. Creates the missing enabled mappings pointing at that channel.
3. Rewrites the Redis routing snapshot.

It never invents a Discord channel. Guilds with no provisioned channel are
skipped.

Usage:
    python -m scripts.backfill_ticket_log_mappings
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session_factory
from app.models.logging_config import (
    LoggingConfiguration,
    LoggingEventMapping,
)
from app.routes.logging_config import _write_routing_snapshot
from app.services.logging_events import GROUP_DEFAULT_COLORS

TICKET_EVENTS = ("ticket_opened", "ticket_closed")
TICKETS_COLOR = GROUP_DEFAULT_COLORS.get("tickets", 0x5865F2)


def _pick_channel(config: LoggingConfiguration):
    """Prefer moderation channel; otherwise first provisioned channel."""

    provisioned = [
        channel
        for channel in config.channels
        if channel.channel_id
    ]
    if not provisioned:
        return None

    for channel in provisioned:
        if channel.key == "moderation":
            return channel
    for channel in provisioned:
        if channel.key == "tickets":
            return channel
    return provisioned[0]


async def main() -> None:
    factory = get_session_factory()
    created = 0
    skipped = 0
    updated_guilds = 0

    async with factory() as session:
        configs = (
            await session.scalars(
                select(LoggingConfiguration)
                .options(
                    selectinload(LoggingConfiguration.channels),
                    selectinload(LoggingConfiguration.event_mappings),
                )
                .where(LoggingConfiguration.status == "active")
            )
        ).all()

        for config in configs:
            existing = {
                mapping.event_type for mapping in config.event_mappings
            }
            missing = [event for event in TICKET_EVENTS if event not in existing]
            if not missing:
                skipped += 1
                continue

            channel = _pick_channel(config)
            if channel is None:
                print(
                    f"skip guild {config.guild_id}: no provisioned channel "
                    f"to attach ticket mappings"
                )
                skipped += 1
                continue

            for event_type in missing:
                mapping = LoggingEventMapping(
                    guild_id=config.guild_id,
                    event_type=event_type,
                    color=TICKETS_COLOR,
                    enabled=True,
                )
                mapping.channel = channel
                config.event_mappings.append(mapping)
                created += 1

            await session.flush()
            # Re-load with relationships for the snapshot writer.
            refreshed = await session.scalar(
                select(LoggingConfiguration)
                .options(
                    selectinload(LoggingConfiguration.channels),
                    selectinload(LoggingConfiguration.event_mappings),
                )
                .where(LoggingConfiguration.id == config.id)
            )
            if refreshed is not None:
                await _write_routing_snapshot(refreshed)
            updated_guilds += 1
            print(
                f"guild {config.guild_id}: added {missing} → "
                f"#{channel.name} ({channel.channel_id})"
            )

        if created:
            await session.commit()

    print(
        f"Done. Created {created} mappings across {updated_guilds} guilds "
        f"({skipped} skipped)."
    )


if __name__ == "__main__":
    asyncio.run(main())
