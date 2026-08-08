"""Business operations for Discord user whitelist and blacklist entries."""

from uuid import UUID

from app.models.enums import UserListType
from app.models.user_list_entry import UserListEntry
from app.repositories.user_list_repository import (
    UserListRepository,
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
    ) -> UserListEntry | None:
        """Return a user's list entry for a Discord guild."""

        return await self._user_list_repository.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )

    async def list_entries(
        self,
        *,
        guild_id: UUID,
        list_type: UserListType | None = None,
    ) -> list[UserListEntry]:
        """Return whitelist or blacklist entries for a guild."""

        return await self._user_list_repository.list_by_guild(
            guild_id=guild_id,
            list_type=list_type,
        )

    async def set_entry(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        list_type: UserListType,
        reason: str | None,
    ) -> UserListEntry:
        """Create or update a user's whitelist or blacklist entry."""

        entry = await self._user_list_repository.get_by_guild_and_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )

        if entry is None:
            entry = UserListEntry(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                list_type=list_type,
                reason=reason,
            )

            return await self._user_list_repository.add(entry)

        entry.list_type = list_type
        entry.reason = reason

        return await self._user_list_repository.save(entry)

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
