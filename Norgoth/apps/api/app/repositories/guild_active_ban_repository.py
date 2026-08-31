"""Database operations for active guild bans."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discord_user import DiscordUser
from app.models.guild_active_ban import GuildActiveBan
from app.models.verification_attempt import VerificationAttempt


class GuildActiveBanRepository:
    """Provide persistence operations for guild-scoped active bans."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_guild_and_user(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> GuildActiveBan | None:
        statement = select(GuildActiveBan).where(
            GuildActiveBan.guild_id == guild_id,
            GuildActiveBan.discord_user_id == discord_user_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def upsert_active_ban(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        username_snapshot: str | None,
        display_name_snapshot: str | None,
        source: str,
        banned_at: datetime | None = None,
    ) -> GuildActiveBan:
        now = banned_at or datetime.now(timezone.utc)
        row = await self.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )
        if row is None:
            row = GuildActiveBan(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                is_active=True,
                banned_at=now,
                username_snapshot=username_snapshot,
                display_name_snapshot=display_name_snapshot,
                source=source,
            )
            self._session.add(row)
        else:
            row.is_active = True
            row.banned_at = now
            row.unbanned_at = None
            row.username_snapshot = username_snapshot or row.username_snapshot
            row.display_name_snapshot = display_name_snapshot or row.display_name_snapshot
            row.source = source
        await self._session.flush()
        return row

    async def deactivate_ban(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        source: str,
        unbanned_at: datetime | None = None,
    ) -> GuildActiveBan | None:
        row = await self.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )
        if row is None:
            return None
        row.is_active = False
        row.unbanned_at = unbanned_at or datetime.now(timezone.utc)
        row.source = source
        await self._session.flush()
        return row

    async def list_active_banned_user_ids(self, *, guild_id: UUID) -> list[str]:
        statement = select(GuildActiveBan.discord_user_id).where(
            GuildActiveBan.guild_id == guild_id,
            GuildActiveBan.is_active.is_(True),
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_active_bans_by_ip_hash(
        self,
        *,
        guild_id: UUID,
        ip_hash: str,
        exclude_discord_user_id: str,
    ) -> list[str]:
        statement = (
            select(GuildActiveBan.discord_user_id)
            .join(
                DiscordUser,
                DiscordUser.discord_user_id == GuildActiveBan.discord_user_id,
            )
            .join(
                VerificationAttempt,
                VerificationAttempt.user_id == DiscordUser.id,
            )
            .where(
                GuildActiveBan.guild_id == guild_id,
                GuildActiveBan.is_active.is_(True),
                VerificationAttempt.guild_id == guild_id,
                VerificationAttempt.ip_hash == ip_hash,
                GuildActiveBan.discord_user_id != exclude_discord_user_id,
            )
            .distinct()
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
