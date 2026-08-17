"""Per-guild per-platform Content Notification configuration limits.

Active caps reduce provider API and Discord rate-limit pressure. Soft total
caps prevent unlimited disabled-row storage abuse. PostgreSQL counts are
authoritative; Redis is not used for quota state.

Limit bibliography (retrieved 2026-08-13):
- Discord global ~50 req/s and per-route buckets:
  https://docs.discord.com/developers/topics/rate-limits
- Twitch EventSub cost-based ``max_total_cost``:
  https://dev.twitch.tv/docs/eventsub/manage-subscriptions/
- YouTube CN path is WebSub-first; Data API quota is project-level.
- X/Twitter CN is poll-only (highest continuous cost) → lower active cap.
- Kick Events is credential-gated → conservative product safety cap.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_notifications import (
    ContentCreatorSource,
    GuildContentSubscription,
)

# Active = enabled=true configurations per guild per platform.
ACTIVE_LIMITS: dict[str, int] = {
    "youtube": 10,
    "twitch": 10,
    "kick": 10,
    "x": 3,
    "tiktok": 0,
}

# Soft total (enabled + disabled) = active_cap * TOTAL_MULTIPLIER.
# Kick is a hard total of 10 including disabled, not 10 × 3.
TOTAL_MULTIPLIER = 3
KICK_TOTAL_LIMIT = 10

CONTENT_NOTIFICATION_LIMIT_REACHED = "content_notification_limit_reached"
CONTENT_NOTIFICATION_TOTAL_LIMIT_REACHED = "content_notification_total_limit_reached"


def active_limit_for(platform: str) -> int:
    return int(ACTIVE_LIMITS.get(platform, 0))


def total_limit_for(platform: str) -> int:
    if platform == "kick":
        return KICK_TOTAL_LIMIT
    active = active_limit_for(platform)
    return active * TOTAL_MULTIPLIER


def _platform_advisory_lock_key(guild_id: str, platform: str) -> int:
    digest = hashlib.blake2b(
        f"norgoth:cn:{guild_id}:{platform}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


async def count_subscriptions(
    session: AsyncSession,
    *,
    guild_id: str,
    platform: str,
    enabled_only: bool,
) -> int:
    stmt = (
        select(func.count())
        .select_from(GuildContentSubscription)
        .join(
            ContentCreatorSource,
            ContentCreatorSource.id == GuildContentSubscription.source_id,
        )
        .where(
            GuildContentSubscription.guild_id == guild_id,
            ContentCreatorSource.platform == platform,
        )
    )
    if enabled_only:
        stmt = stmt.where(GuildContentSubscription.enabled.is_(True))
    result = await session.scalar(stmt)
    return int(result or 0)


async def platform_usage(
    session: AsyncSession,
    *,
    guild_id: str,
    platform: str,
) -> dict[str, Any]:
    active_limit = active_limit_for(platform)
    total_limit = total_limit_for(platform)
    active_count = await count_subscriptions(
        session, guild_id=guild_id, platform=platform, enabled_only=True
    )
    total_count = await count_subscriptions(
        session, guild_id=guild_id, platform=platform, enabled_only=False
    )
    return {
        "platform": platform,
        "active_limit": active_limit,
        "active_count": active_count,
        "active_remaining": max(0, active_limit - active_count),
        "total_limit": total_limit,
        "total_count": total_count,
        "total_remaining": max(0, total_limit - total_count),
    }


async def guild_platform_usage(
    session: AsyncSession,
    *,
    guild_id: str,
) -> list[dict[str, Any]]:
    return [
        await platform_usage(session, guild_id=guild_id, platform=platform)
        for platform in ACTIVE_LIMITS
    ]


class ContentNotificationQuotaError(Exception):
    """Raised when create/enable would exceed a configured limit."""

    def __init__(
        self,
        *,
        code: str,
        platform: str,
        limit: int,
        current: int,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.platform = platform
        self.limit = limit
        self.current = current
        self.message = message

    def as_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "platform": self.platform,
            "limit": self.limit,
            "current": self.current,
        }


async def _lock_platform_subscriptions(
    session: AsyncSession,
    *,
    guild_id: str,
    platform: str,
) -> None:
    """Serialize concurrent create/enable for the same guild+platform."""

    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _platform_advisory_lock_key(guild_id, platform)},
    )
    await session.scalars(
        select(GuildContentSubscription.id)
        .join(
            ContentCreatorSource,
            ContentCreatorSource.id == GuildContentSubscription.source_id,
        )
        .where(
            GuildContentSubscription.guild_id == guild_id,
            ContentCreatorSource.platform == platform,
        )
        .with_for_update()
    )


async def assert_can_create(
    session: AsyncSession,
    *,
    guild_id: str,
    platform: str,
    will_be_enabled: bool,
) -> None:
    """Enforce active + soft total caps before inserting a new subscription."""

    await _lock_platform_subscriptions(
        session, guild_id=guild_id, platform=platform
    )
    usage = await platform_usage(session, guild_id=guild_id, platform=platform)
    if usage["total_count"] >= usage["total_limit"]:
        raise ContentNotificationQuotaError(
            code=CONTENT_NOTIFICATION_TOTAL_LIMIT_REACHED,
            platform=platform,
            limit=usage["total_limit"],
            current=usage["total_count"],
            message=(
                f"Maximum of {usage['total_limit']} {platform} configurations "
                f"per server (including disabled)."
            ),
        )
    if will_be_enabled and usage["active_count"] >= usage["active_limit"]:
        raise ContentNotificationQuotaError(
            code=CONTENT_NOTIFICATION_LIMIT_REACHED,
            platform=platform,
            limit=usage["active_limit"],
            current=usage["active_count"],
            message=(
                f"Maximum of {usage['active_limit']} active {platform} "
                f"configurations per server."
            ),
        )


async def assert_can_enable(
    session: AsyncSession,
    *,
    guild_id: str,
    platform: str,
    currently_enabled: bool,
) -> None:
    """Enforce active cap when flipping a disabled subscription to enabled."""

    if currently_enabled:
        return
    await _lock_platform_subscriptions(
        session, guild_id=guild_id, platform=platform
    )
    usage = await platform_usage(session, guild_id=guild_id, platform=platform)
    if usage["active_count"] >= usage["active_limit"]:
        raise ContentNotificationQuotaError(
            code=CONTENT_NOTIFICATION_LIMIT_REACHED,
            platform=platform,
            limit=usage["active_limit"],
            current=usage["active_count"],
            message=(
                f"Maximum of {usage['active_limit']} active {platform} "
                f"configurations per server."
            ),
        )
