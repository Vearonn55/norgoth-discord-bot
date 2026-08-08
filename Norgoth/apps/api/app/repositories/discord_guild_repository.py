"""Database operations for Discord guilds."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discord_guild import DiscordGuild


class DiscordGuildRepository:
    """Provide persistence operations for Discord guilds."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_id(self, guild_id: UUID) -> DiscordGuild | None:
        """Return a Discord guild by its internal UUID."""

        return await self._session.get(DiscordGuild, guild_id)

    async def get_by_discord_guild_id(
        self,
        discord_guild_id: str,
    ) -> DiscordGuild | None:
        """Return a guild by its Discord snowflake."""

        statement = select(DiscordGuild).where(DiscordGuild.discord_guild_id == discord_guild_id)
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def add(self, guild: DiscordGuild) -> DiscordGuild:
        """Add a Discord guild and flush it to the database."""

        self._session.add(guild)
        await self._session.flush()

        return guild

    async def save(self, guild: DiscordGuild) -> DiscordGuild:
        """Flush changes made to an existing Discord guild."""

        await self._session.flush()

        return guild

    async def delete(self, guild: DiscordGuild) -> None:
        """Delete a Discord guild and flush the change."""

        await self._session.delete(guild)
        await self._session.flush()
