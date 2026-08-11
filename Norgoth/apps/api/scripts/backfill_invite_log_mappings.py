"""Backfill invite_member_joined / invite_member_left logging mappings.

Guilds whose Logging Configuration was saved before the Invites group was
added have no invite event mappings, so the bot's routing snapshot silently
drops those events.

Idempotent and opt-in. Prefer an existing ``invites`` channel, else
``member``, else the first provisioned channel. Never invents a Discord channel.

Usage:
    python -m scripts.backfill_invite_log_mappings
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

INVITE_EVENTS = ("invite_member_joined", "invite_member_left")
INVITES_COLOR = GROUP_DEFAULT_COLORS.get("invites", 0x57F287)


def _pick_channel(config: LoggingConfiguration):
    provisioned = [c for c in config.channels if c.channel_id]
    if not provisioned:
        return None
    for key in ("invites", "member", "moderation"):
        for channel in provisioned:
            if channel.key == key:
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
            existing = {m.event_type for m in config.event_mappings}
            missing = [e for e in INVITE_EVENTS if e not in existing]
            if not missing:
                skipped += 1
                continue

            channel = _pick_channel(config)
            if channel is None:
                print(
                    f"skip guild {config.guild_id}: no provisioned channel"
                )
                skipped += 1
                continue

            for event_type in missing:
                mapping = LoggingEventMapping(
                    guild_id=config.guild_id,
                    event_type=event_type,
                    color=INVITES_COLOR,
                    enabled=True,
                )
                mapping.channel = channel
                config.event_mappings.append(mapping)
                created += 1

            await session.flush()
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
