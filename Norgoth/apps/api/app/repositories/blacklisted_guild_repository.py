"""Database operations for blacklisted Discord guilds."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklisted_guild import BlacklistedGuild


class BlacklistedGuildRepository:
    """Provide persistence operations for blacklisted Discord guilds."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_owner_and_target(
        self,
        *,
        guild_id: UUID,
        blacklisted_discord_guild_id: str,
    ) -> BlacklistedGuild | None:
        """Return a blacklisted guild entry by owner and target IDs."""

        statement = select(BlacklistedGuild).where(
            BlacklistedGuild.guild_id == guild_id,
            BlacklistedGuild.blacklisted_discord_guild_id == blacklisted_discord_guild_id,
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_guild(
        self,
        guild_id: UUID,
    ) -> list[BlacklistedGuild]:
        """Return blacklisted Discord guilds configured by one guild."""

        statement = (
            select(BlacklistedGuild)
            .where(BlacklistedGuild.guild_id == guild_id)
            .order_by(BlacklistedGuild.created_at.desc())
        )
        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def add(
        self,
        entry: BlacklistedGuild,
    ) -> BlacklistedGuild:
        """Add a blacklisted guild entry and flush it."""

        self._session.add(entry)
        await self._session.flush()

        return entry

    async def save(
        self,
        entry: BlacklistedGuild,
    ) -> BlacklistedGuild:
        """Flush changes made to an existing blacklisted guild entry."""

        await self._session.flush()

        return entry

    async def delete(
        self,
        entry: BlacklistedGuild,
    ) -> None:
        """Delete a blacklisted guild entry and flush the change."""

        await self._session.delete(entry)
        await self._session.flush()
