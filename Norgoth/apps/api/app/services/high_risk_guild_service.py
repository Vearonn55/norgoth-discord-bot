"""Business operations for high-risk Discord guilds."""

from uuid import UUID

from app.models.guild_high_risk_guild import GuildHighRiskGuild
from app.repositories.high_risk_guild_repository import (
    HighRiskGuildRepository,
)


class HighRiskGuildService:
    """Manage per-guild high-risk Discord server entries."""

    def __init__(
        self,
        high_risk_guild_repository: HighRiskGuildRepository,
    ) -> None:
        """Initialize the service with its repository."""

        self._high_risk_guild_repository = high_risk_guild_repository

    async def get_entry(
        self,
        *,
        guild_id: UUID,
        high_risk_discord_guild_id: str,
    ) -> GuildHighRiskGuild | None:
        """Return one high-risk Discord guild entry."""

        return await self._high_risk_guild_repository.get_by_owner_and_target(
            guild_id=guild_id,
            high_risk_discord_guild_id=high_risk_discord_guild_id,
        )

    async def list_entries(
        self,
        guild_id: UUID,
    ) -> list[GuildHighRiskGuild]:
        """Return all high-risk Discord guilds for one server."""

        return await self._high_risk_guild_repository.list_by_guild(guild_id)

    async def set_entry(
        self,
        *,
        guild_id: UUID,
        high_risk_discord_guild_id: str,
        reason: str | None,
        created_by: str | None,
    ) -> GuildHighRiskGuild:
        """Create or update a high-risk Discord guild entry."""

        entry = await self._high_risk_guild_repository.get_by_owner_and_target(
            guild_id=guild_id,
            high_risk_discord_guild_id=high_risk_discord_guild_id,
        )

        if entry is None:
            entry = GuildHighRiskGuild(
                guild_id=guild_id,
                high_risk_discord_guild_id=high_risk_discord_guild_id,
                reason=reason,
                created_by=created_by,
            )

            return await self._high_risk_guild_repository.add(entry)

        entry.reason = reason

        return await self._high_risk_guild_repository.save(entry)

    async def remove_entry(
        self,
        *,
        guild_id: UUID,
        high_risk_discord_guild_id: str,
    ) -> bool:
        """Remove a high-risk Discord guild entry."""

        entry = await self._high_risk_guild_repository.get_by_owner_and_target(
            guild_id=guild_id,
            high_risk_discord_guild_id=high_risk_discord_guild_id,
        )

        if entry is None:
            return False

        await self._high_risk_guild_repository.delete(entry)

        return True
