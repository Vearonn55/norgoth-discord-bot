"""Business operations for blacklisted Discord guilds."""

from uuid import UUID

from app.models.blacklisted_guild import BlacklistedGuild
from app.repositories.blacklisted_guild_repository import (
    BlacklistedGuildRepository,
)


class BlacklistedGuildService:
    """Manage per-guild Discord server blacklist entries."""

    def __init__(
        self,
        blacklisted_guild_repository: BlacklistedGuildRepository,
    ) -> None:
        """Initialize the service with its repository."""

        self._blacklisted_guild_repository = blacklisted_guild_repository

    async def get_entry(
        self,
        *,
        guild_id: UUID,
        blacklisted_discord_guild_id: str,
    ) -> BlacklistedGuild | None:
        """Return one blacklisted Discord guild entry."""

        return await self._blacklisted_guild_repository.get_by_owner_and_target(
            guild_id=guild_id,
            blacklisted_discord_guild_id=(blacklisted_discord_guild_id),
        )

    async def list_entries(
        self,
        guild_id: UUID,
    ) -> list[BlacklistedGuild]:
        """Return all blacklisted Discord guilds for one server."""

        return await self._blacklisted_guild_repository.list_by_guild(guild_id)

    async def set_entry(
        self,
        *,
        guild_id: UUID,
        blacklisted_discord_guild_id: str,
        reason: str | None,
    ) -> BlacklistedGuild:
        """Create or update a blacklisted Discord guild entry."""

        entry = await self._blacklisted_guild_repository.get_by_owner_and_target(
            guild_id=guild_id,
            blacklisted_discord_guild_id=(blacklisted_discord_guild_id),
        )

        if entry is None:
            entry = BlacklistedGuild(
                guild_id=guild_id,
                blacklisted_discord_guild_id=(blacklisted_discord_guild_id),
                reason=reason,
            )

            return await self._blacklisted_guild_repository.add(entry)

        entry.reason = reason

        return await self._blacklisted_guild_repository.save(entry)

    async def remove_entry(
        self,
        *,
        guild_id: UUID,
        blacklisted_discord_guild_id: str,
    ) -> bool:
        """Remove a blacklisted Discord guild entry."""

        entry = await self._blacklisted_guild_repository.get_by_owner_and_target(
            guild_id=guild_id,
            blacklisted_discord_guild_id=(blacklisted_discord_guild_id),
        )

        if entry is None:
            return False

        await self._blacklisted_guild_repository.delete(entry)

        return True
