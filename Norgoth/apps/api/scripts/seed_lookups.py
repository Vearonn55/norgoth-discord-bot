"""Seed the reference/lookup dimensions for the Postgres source of truth.

Idempotent: upserts platforms, content event types, and Discord logging event
types (from the wizard catalog). Safe to run repeatedly.

Usage:
    python -m scripts.seed_lookups
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.content_lookups import ContentEventType, Platform
from app.models.logging_config import DiscordLoggingEventType
from app.services.logging_events import EVENT_GROUPS, GROUP_DEFAULT_COLORS

# platform key -> (display name, [(event key, display name), ...])
PLATFORM_SEED: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "twitch": ("Twitch", [("twitch.live", "Went live"), ("twitch.offline", "Went offline")]),
    "youtube": ("YouTube", [("youtube.upload", "New upload"), ("youtube.live", "Went live")]),
    "tiktok": ("TikTok", [("tiktok.post", "New post")]),
    "kick": ("Kick", [("kick.live", "Went live")]),
    "x": ("X", [("x.post", "New post")]),
}


async def _seed_platforms(session) -> None:
    existing = {
        row.key: row
        for row in (await session.execute(select(Platform))).scalars().all()
    }
    for key, (display, event_types) in PLATFORM_SEED.items():
        platform = existing.get(key)
        if platform is None:
            platform = Platform(key=key, display_name=display, enabled=True)
            session.add(platform)
            await session.flush()
        else:
            platform.display_name = display

        existing_events = {
            row.key
            for row in (
                await session.execute(
                    select(ContentEventType).where(
                        ContentEventType.platform_id == platform.id
                    )
                )
            )
            .scalars()
            .all()
        }
        for event_key, event_display in event_types:
            if event_key in existing_events:
                continue
            session.add(
                ContentEventType(
                    platform_id=platform.id,
                    key=event_key,
                    display_name=event_display,
                    enabled=True,
                )
            )


async def _seed_logging_event_types(session) -> None:
    existing = {
        row.key: row
        for row in (await session.execute(select(DiscordLoggingEventType)))
        .scalars()
        .all()
    }
    for group_key, group in EVENT_GROUPS.items():
        default_color = GROUP_DEFAULT_COLORS.get(group_key)
        for event_type, label in group["events"]:
            row = existing.get(event_type)
            if row is None:
                session.add(
                    DiscordLoggingEventType(
                        key=event_type,
                        group_key=group_key,
                        label=label,
                        default_color=default_color,
                    )
                )
            else:
                row.group_key = group_key
                row.label = label
                if default_color is not None:
                    row.default_color = default_color


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await _seed_platforms(session)
        await _seed_logging_event_types(session)
        await session.commit()
    print("Seeded platforms, content event types, and logging event types.")


if __name__ == "__main__":
    asyncio.run(main())
