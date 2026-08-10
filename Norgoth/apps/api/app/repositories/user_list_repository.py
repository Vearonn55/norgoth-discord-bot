"""Database operations for guild moderation (whitelist/blacklist) entries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discord_user import DiscordUser
from app.models.enums import UserListType
from app.models.guild_moderation_entry import GuildModerationEntry


class UserListRepository:
    """Provide persistence operations for guild moderation entries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_guild_and_user(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> GuildModerationEntry | None:
        """Return a user's moderation entry for a guild, if any."""

        statement = (
            select(GuildModerationEntry)
            .join(DiscordUser, GuildModerationEntry.user_id == DiscordUser.id)
            .where(
                GuildModerationEntry.guild_id == guild_id,
                DiscordUser.discord_user_id == discord_user_id,
            )
            .options(selectinload(GuildModerationEntry.user))
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_guild(
        self,
        *,
        guild_id: UUID,
        list_type: UserListType | None = None,
    ) -> list[GuildModerationEntry]:
        """Return moderation entries belonging to a Discord guild."""

        statement = (
            select(GuildModerationEntry)
            .where(GuildModerationEntry.guild_id == guild_id)
            .options(selectinload(GuildModerationEntry.user))
        )

        if list_type is not None:
            statement = statement.where(GuildModerationEntry.list_type == list_type)

        statement = statement.order_by(GuildModerationEntry.created_at.desc())

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def set_entry(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        list_type: UserListType,
        reason: str | None,
    ) -> GuildModerationEntry:
        """Create or update a user's moderation entry (upserting the user)."""

        from app.services.users import upsert_discord_user

        user = await upsert_discord_user(self._session, discord_user_id)

        entry = await self.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )

        if entry is None:
            entry = GuildModerationEntry(
                guild_id=guild_id,
                user_id=user.id,
                list_type=list_type,
                reason=reason,
            )
            self._session.add(entry)
            await self._session.flush()
            entry.user = user
            return entry

        entry.list_type = list_type
        entry.reason = reason
        await self._session.flush()

        return entry

    async def delete(self, entry: GuildModerationEntry) -> None:
        """Delete a moderation entry and flush the change."""

        await self._session.delete(entry)
        await self._session.flush()
