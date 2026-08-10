"""Database operations for high-risk Discord guilds."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guild_high_risk_guild import GuildHighRiskGuild


class HighRiskGuildRepository:
    """Provide persistence operations for high-risk Discord guilds."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_owner_and_target(
        self,
        *,
        guild_id: UUID,
        high_risk_discord_guild_id: str,
    ) -> GuildHighRiskGuild | None:
        """Return a high-risk guild entry by owner and target IDs."""

        statement = select(GuildHighRiskGuild).where(
            GuildHighRiskGuild.guild_id == guild_id,
            GuildHighRiskGuild.high_risk_discord_guild_id
            == high_risk_discord_guild_id,
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_guild(
        self,
        guild_id: UUID,
    ) -> list[GuildHighRiskGuild]:
        """Return high-risk Discord guilds configured by one guild."""

        statement = (
            select(GuildHighRiskGuild)
            .where(GuildHighRiskGuild.guild_id == guild_id)
            .order_by(GuildHighRiskGuild.created_at.desc())
        )
        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def add(
        self,
        entry: GuildHighRiskGuild,
    ) -> GuildHighRiskGuild:
        """Add a high-risk guild entry and flush it."""

        self._session.add(entry)
        await self._session.flush()

        return entry

    async def save(
        self,
        entry: GuildHighRiskGuild,
    ) -> GuildHighRiskGuild:
        """Flush changes made to an existing high-risk guild entry."""

        await self._session.flush()

        return entry

    async def delete(
        self,
        entry: GuildHighRiskGuild,
    ) -> None:
        """Delete a high-risk guild entry and flush the change."""

        await self._session.delete(entry)
        await self._session.flush()
