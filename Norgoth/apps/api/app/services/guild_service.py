"""Business operations for registered Discord guilds."""

from app.models.discord_guild import DiscordGuild
from app.repositories.discord_guild_repository import (
    DiscordGuildRepository,
)


class GuildService:
    """Manage Discord guild registration and lifecycle operations."""

    def __init__(
        self,
        guild_repository: DiscordGuildRepository,
    ) -> None:
        """Initialize the service with its guild repository."""

        self._guild_repository = guild_repository

    async def get_by_discord_guild_id(
        self,
        discord_guild_id: str,
    ) -> DiscordGuild | None:
        """Return a registered guild by its Discord snowflake."""

        return await self._guild_repository.get_by_discord_guild_id(discord_guild_id)

    async def register_or_update(
        self,
        *,
        discord_guild_id: str,
        discord_guild_name: str,
        discord_owner_id: str,
    ) -> DiscordGuild:
        """Create a guild record or update its current Discord metadata."""

        guild = await self._guild_repository.get_by_discord_guild_id(discord_guild_id)

        if guild is None:
            guild = DiscordGuild(
                discord_guild_id=discord_guild_id,
                discord_guild_name=discord_guild_name,
                discord_owner_id=discord_owner_id,
            )

            return await self._guild_repository.add(guild)

        guild.discord_guild_name = discord_guild_name
        guild.discord_owner_id = discord_owner_id

        return await self._guild_repository.save(guild)

    async def remove(
        self,
        discord_guild_id: str,
    ) -> bool:
        """Remove a registered guild and all of its owned records."""

        guild = await self._guild_repository.get_by_discord_guild_id(discord_guild_id)

        if guild is None:
            return False

        await self._guild_repository.delete(guild)

        return True
