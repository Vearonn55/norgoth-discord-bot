"""Backfill disabled logging_event_mappings for newly catalogued event types.

Existing guilds keep current effective behaviour: new event types are attached
to the matching category channel with ``enabled=false`` until an admin opts in.

Usage:
    python -m scripts.backfill_new_logging_events
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session_factory
from app.models.logging_config import (
    DiscordLoggingEventType,
    LoggingConfiguration,
    LoggingEventMapping,
)
from app.routes.logging_config import _write_routing_snapshot
from app.services.logging_events import (
    EVENT_GROUPS,
    GROUP_DEFAULT_COLORS,
    NEW_EVENT_TYPES_DEFAULT_OFF,
    group_for_event,
)


async def main() -> None:
    factory = get_session_factory()
    created = 0
    async with factory() as session:
        # Ensure lookup rows exist for new types.
        existing_types = {
            row.key: row
            for row in (
                await session.execute(select(DiscordLoggingEventType))
            ).scalars().all()
        }
        for group_key, group in EVENT_GROUPS.items():
            color = GROUP_DEFAULT_COLORS.get(group_key)
            for event_type, label in group["events"]:
                if event_type in existing_types:
                    continue
                row = DiscordLoggingEventType(
                    key=event_type,
                    group_key=group_key,
                    label=label,
                    default_color=color,
                )
                session.add(row)
                existing_types[event_type] = row
        await session.flush()

        configs = (
            await session.execute(
                select(LoggingConfiguration).options(
                    selectinload(LoggingConfiguration.channels),
                    selectinload(LoggingConfiguration.events),
                )
            )
        ).scalars().all()

        for config in configs:
            existing_event_types = {e.event_type for e in config.events}
            channels_by_key = {c.key: c for c in config.channels}
            dirty = False
            for event_type in NEW_EVENT_TYPES_DEFAULT_OFF:
                if event_type in existing_event_types:
                    continue
                group_key = group_for_event(event_type)
                if not group_key:
                    continue
                channel = channels_by_key.get(group_key)
                if channel is None:
                    continue
                lookup = existing_types.get(event_type)
                session.add(
                    LoggingEventMapping(
                        logging_configuration_id=config.id,
                        logging_channel_id=channel.id,
                        event_type=event_type,
                        event_type_id=lookup.id if lookup else None,
                        color=None,
                        enabled=False,
                    )
                )
                created += 1
                dirty = True
            if dirty:
                await session.flush()
                await session.refresh(
                    config,
                    attribute_names=["channels", "events"],
                )
                await _write_routing_snapshot(config)

        await session.commit()

    print(f"backfill_new_logging_events: created={created} disabled mappings")


if __name__ == "__main__":
    asyncio.run(main())
