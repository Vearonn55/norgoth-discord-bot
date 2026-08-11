"""Business operations for registered Discord guilds."""

from app.models.guild import Guild
from app.repositories.discord_guild_repository import (
    DiscordGuildRepository,
)
from app.services.views import GuildView


def _to_view(guild: Guild) -> GuildView:
    """Assemble a flat ``GuildView`` from a ``Guild`` ORM row."""

    owner_snowflake = guild.owner.discord_user_id if guild.owner is not None else ""

    return GuildView(
        id=guild.id,
        discord_guild_id=guild.discord_guild_id,
        discord_guild_name=guild.name,
        discord_owner_id=owner_snowflake,
        created_at=guild.created_at,
        updated_at=guild.updated_at,
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
    ) -> GuildView | None:
        """Return a registered guild by its Discord snowflake."""

        guild = await self._guild_repository.get_by_discord_guild_id(discord_guild_id)

        return _to_view(guild) if guild is not None else None

    async def register_or_update(
        self,
        *,
        discord_guild_id: str,
        discord_guild_name: str,
        discord_owner_id: str,
    ) -> GuildView:
        """Create a guild record or update its current Discord metadata."""

        owner = await self._guild_repository.resolve_owner(discord_owner_id)

        guild = await self._guild_repository.get_by_discord_guild_id(discord_guild_id)

        if guild is None:
            guild = Guild(
                discord_guild_id=discord_guild_id,
                name=discord_guild_name,
                owner_user_id=owner.id,
            )
            guild = await self._guild_repository.add(guild)
            guild.owner = owner
            return _to_view(guild)

        guild.name = discord_guild_name
        guild.owner_user_id = owner.id
        guild = await self._guild_repository.save(guild)
        guild.owner = owner

        return _to_view(guild)

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
