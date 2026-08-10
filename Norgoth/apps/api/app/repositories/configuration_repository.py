"""Database operations for normalized guild verification configuration."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GuildChannelPurpose, GuildRolePurpose
from app.models.guild_bindings import GuildChannelBinding, GuildRoleBinding
from app.models.guild_settings import GuildSettings


class ConfigurationRepository:
    """Persist guild settings plus their role and channel bindings."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_settings(self, guild_id: UUID) -> GuildSettings | None:
        """Return the settings row for a guild, if any."""

        statement = select(GuildSettings).where(GuildSettings.guild_id == guild_id)
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def get_role_bindings(
        self,
        guild_id: UUID,
    ) -> dict[GuildRolePurpose, GuildRoleBinding]:
        """Return role bindings for a guild keyed by purpose."""

        statement = select(GuildRoleBinding).where(GuildRoleBinding.guild_id == guild_id)
        result = await self._session.execute(statement)

        return {binding.purpose: binding for binding in result.scalars().all()}

    async def get_channel_bindings(
        self,
        guild_id: UUID,
    ) -> dict[GuildChannelPurpose, GuildChannelBinding]:
        """Return channel bindings for a guild keyed by purpose."""

        statement = select(GuildChannelBinding).where(
            GuildChannelBinding.guild_id == guild_id
        )
        result = await self._session.execute(statement)

        return {binding.purpose: binding for binding in result.scalars().all()}

    async def add(self, instance: object) -> None:
        """Stage a new settings/binding row on the session."""

        self._session.add(instance)

    async def delete(self, instance: object) -> None:
        """Stage a settings/binding row for deletion."""

        await self._session.delete(instance)

    async def flush(self) -> None:
        """Flush pending changes to the database."""

        await self._session.flush()
