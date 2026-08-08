"""Database operations for Discord guild configurations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration


class ConfigurationRepository:
    """Provide persistence operations for guild configurations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_id(
        self,
        configuration_id: UUID,
    ) -> Configuration | None:
        """Return a configuration by its internal UUID."""

        return await self._session.get(Configuration, configuration_id)

    async def get_by_guild_id(
        self,
        guild_id: UUID,
    ) -> Configuration | None:
        """Return the configuration belonging to a Discord guild."""

        statement = select(Configuration).where(Configuration.guild_id == guild_id)
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def add(
        self,
        configuration: Configuration,
    ) -> Configuration:
        """Add a guild configuration and flush it to the database."""

        self._session.add(configuration)
        await self._session.flush()

        return configuration

    async def save(
        self,
        configuration: Configuration,
    ) -> Configuration:
        """Flush changes made to an existing configuration."""

        await self._session.flush()

        return configuration

    async def delete(
        self,
        configuration: Configuration,
    ) -> None:
        """Delete a guild configuration and flush the change."""

        await self._session.delete(configuration)
        await self._session.flush()
