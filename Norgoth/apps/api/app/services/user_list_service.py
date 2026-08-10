"""Business operations for guild moderation (whitelist/blacklist) entries."""

from uuid import UUID

from app.models.enums import UserListType
from app.models.guild_moderation_entry import GuildModerationEntry
from app.repositories.user_list_repository import (
    UserListRepository,
)
from app.services.views import ModerationEntryView


def _to_view(entry: GuildModerationEntry) -> ModerationEntryView:
    """Assemble a flat view from a moderation entry (user eager-loaded)."""

    return ModerationEntryView(
        id=entry.id,
        guild_id=entry.guild_id,
        discord_user_id=entry.user.discord_user_id,
        list_type=entry.list_type,
        reason=entry.reason,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


class UserListService:
    """Manage per-guild Discord user whitelist and blacklist entries."""

    def __init__(
        self,
        user_list_repository: UserListRepository,
    ) -> None:
        """Initialize the service with its repository."""

        self._user_list_repository = user_list_repository

    async def get_entry(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> GuildModerationEntry | None:
        """Return a user's moderation entry (ORM) for a Discord guild."""

        return await self._user_list_repository.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )

    async def list_entries(
        self,
        *,
        guild_id: UUID,
        list_type: UserListType | None = None,
    ) -> list[ModerationEntryView]:
        """Return whitelist or blacklist entries for a guild."""

        entries = await self._user_list_repository.list_by_guild(
            guild_id=guild_id,
            list_type=list_type,
        )

        return [_to_view(entry) for entry in entries]

    async def set_entry(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        list_type: UserListType,
        reason: str | None,
    ) -> ModerationEntryView:
        """Create or update a user's whitelist or blacklist entry."""

        entry = await self._user_list_repository.set_entry(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            list_type=list_type,
            reason=reason,
        )

        return _to_view(entry)

    async def remove_entry(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> bool:
        """Remove a user's whitelist or blacklist entry."""

        entry = await self._user_list_repository.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )

        if entry is None:
            return False

        await self._user_list_repository.delete(entry)

        return True
