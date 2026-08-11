"""Upsert helper for the central ``discord_users`` dimension."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discord_user import DiscordUser


async def upsert_discord_user(
    session: AsyncSession,
    discord_user_id: str,
    *,
    username: str | None = None,
) -> DiscordUser:
    """Return the ``DiscordUser`` for ``discord_user_id``, creating it if needed.

    Updates the cached username and ``last_seen_at`` when the row already exists.
    The caller owns the commit boundary; this only stages changes on the session.
    """

    result = await session.execute(
        select(DiscordUser).where(DiscordUser.discord_user_id == discord_user_id)
    )
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if user is None:
        user = DiscordUser(
            discord_user_id=discord_user_id,
            username_cache=username,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(user)
        await session.flush()
        return user

    user.last_seen_at = now
    if username is not None:
        user.username_cache = username
    return user
