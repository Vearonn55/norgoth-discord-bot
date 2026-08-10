"""Database operations for Discord guilds."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discord_user import DiscordUser
from app.models.guild import Guild


class DiscordGuildRepository:
    """Provide persistence operations for Discord guilds."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_id(self, guild_id: UUID) -> Guild | None:
        """Return a guild by its internal UUID (owner eager-loaded)."""

        statement = (
            select(Guild).where(Guild.id == guild_id).options(selectinload(Guild.owner))
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_discord_guild_id(
        self,
        discord_guild_id: str,
    ) -> Guild | None:
        """Return a guild by its Discord snowflake (owner eager-loaded)."""

        statement = (
            select(Guild)
            .where(Guild.discord_guild_id == discord_guild_id)
            .options(selectinload(Guild.owner))
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def resolve_owner(self, discord_owner_id: str) -> DiscordUser:
        """Return (creating if needed) the ``DiscordUser`` for an owner."""

        from app.services.users import upsert_discord_user

        return await upsert_discord_user(self._session, discord_owner_id)

    async def add(self, guild: Guild) -> Guild:
        """Add a guild and flush it to the database."""

        self._session.add(guild)
        await self._session.flush()

        return guild

    async def save(self, guild: Guild) -> Guild:
        """Flush changes made to an existing guild."""

        await self._session.flush()

        return guild

    async def delete(self, guild: Guild) -> None:
        """Delete a guild and flush the change."""

        await self._session.delete(guild)
        await self._session.flush()
