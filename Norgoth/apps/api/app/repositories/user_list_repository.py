"""Database operations for Discord user whitelist and blacklist entries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserListType
from app.models.user_list_entry import UserListEntry


class UserListRepository:
    """Provide persistence operations for user list entries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def get_by_guild_and_user(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> UserListEntry | None:
        """Return a user's whitelist or blacklist entry for a guild."""

        statement = select(UserListEntry).where(
            UserListEntry.guild_id == guild_id,
            UserListEntry.discord_user_id == discord_user_id,
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_guild(
        self,
        *,
        guild_id: UUID,
        list_type: UserListType | None = None,
    ) -> list[UserListEntry]:
        """Return user list entries belonging to a Discord guild."""

        statement = select(UserListEntry).where(UserListEntry.guild_id == guild_id)

        if list_type is not None:
            statement = statement.where(UserListEntry.list_type == list_type)

        statement = statement.order_by(UserListEntry.created_at.desc())

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def add(
        self,
        entry: UserListEntry,
    ) -> UserListEntry:
        """Add a user list entry and flush it to the database."""

        self._session.add(entry)
        await self._session.flush()

        return entry

    async def save(
        self,
        entry: UserListEntry,
    ) -> UserListEntry:
        """Flush changes made to an existing user list entry."""

        await self._session.flush()

        return entry

    async def delete(
        self,
        entry: UserListEntry,
    ) -> None:
        """Delete a user list entry and flush the change."""

        await self._session.delete(entry)
        await self._session.flush()
