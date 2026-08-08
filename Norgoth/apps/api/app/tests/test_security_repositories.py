"""Tests for verification security repositories."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklisted_guild import BlacklistedGuild
from app.models.enums import UserListType
from app.models.user_list_entry import UserListEntry
from app.models.verification_log import VerificationLog
from app.repositories.blacklisted_guild_repository import (
    BlacklistedGuildRepository,
)
from app.repositories.user_list_repository import (
    UserListRepository,
)
from app.repositories.verification_log_repository import (
    VerificationLogRepository,
)


@pytest.mark.anyio
async def test_user_list_repository_get_by_guild_and_user() -> None:
    """A user list entry should be retrievable by guild and user."""

    guild_id = uuid4()
    entry = MagicMock(spec=UserListEntry)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = entry

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=scalar_result)

    repository = UserListRepository(session)

    result = await repository.get_by_guild_and_user(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
    )

    assert result is entry
    session.execute.assert_awaited_once()
    scalar_result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.anyio
async def test_user_list_repository_list_by_guild() -> None:
    """User list entries should be returned for a guild."""

    guild_id = uuid4()
    entry = MagicMock(spec=UserListEntry)

    scalars = MagicMock()
    scalars.all.return_value = [entry]

    result_proxy = MagicMock()
    result_proxy.scalars.return_value = scalars

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_proxy)

    repository = UserListRepository(session)

    result = await repository.list_by_guild(
        guild_id=guild_id,
        list_type=UserListType.BLACKLIST,
    )

    assert result == [entry]
    session.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_user_list_repository_add() -> None:
    """Adding a user list entry should add and flush it."""

    entry = MagicMock(spec=UserListEntry)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = UserListRepository(session)

    result = await repository.add(entry)

    assert result is entry
    session.add.assert_called_once_with(entry)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_user_list_repository_save() -> None:
    """Saving a user list entry should flush pending changes."""

    entry = MagicMock(spec=UserListEntry)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = UserListRepository(session)

    result = await repository.save(entry)

    assert result is entry
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_user_list_repository_delete() -> None:
    """Deleting a user list entry should delete and flush it."""

    entry = MagicMock(spec=UserListEntry)

    session = MagicMock(spec=AsyncSession)
    session.delete = AsyncMock()
    session.flush = AsyncMock()

    repository = UserListRepository(session)

    await repository.delete(entry)

    session.delete.assert_awaited_once_with(entry)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_blacklisted_guild_repository_get_by_owner_and_target() -> None:
    """A blacklisted guild should be retrievable by owner and target."""

    guild_id = uuid4()
    entry = MagicMock(spec=BlacklistedGuild)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = entry

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=scalar_result)

    repository = BlacklistedGuildRepository(session)

    result = await repository.get_by_owner_and_target(
        guild_id=guild_id,
        blacklisted_discord_guild_id="123456789012345678",
    )

    assert result is entry
    session.execute.assert_awaited_once()
    scalar_result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.anyio
async def test_blacklisted_guild_repository_list_by_guild() -> None:
    """Blacklisted guild entries should be returned for a guild."""

    guild_id = uuid4()
    entry = MagicMock(spec=BlacklistedGuild)

    scalars = MagicMock()
    scalars.all.return_value = [entry]

    result_proxy = MagicMock()
    result_proxy.scalars.return_value = scalars

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_proxy)

    repository = BlacklistedGuildRepository(session)

    result = await repository.list_by_guild(guild_id)

    assert result == [entry]
    session.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_blacklisted_guild_repository_add() -> None:
    """Adding a blacklisted guild should add and flush it."""

    entry = MagicMock(spec=BlacklistedGuild)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = BlacklistedGuildRepository(session)

    result = await repository.add(entry)

    assert result is entry
    session.add.assert_called_once_with(entry)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_blacklisted_guild_repository_save() -> None:
    """Saving a blacklisted guild should flush pending changes."""

    entry = MagicMock(spec=BlacklistedGuild)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = BlacklistedGuildRepository(session)

    result = await repository.save(entry)

    assert result is entry
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_blacklisted_guild_repository_delete() -> None:
    """Deleting a blacklisted guild should delete and flush it."""

    entry = MagicMock(spec=BlacklistedGuild)

    session = MagicMock(spec=AsyncSession)
    session.delete = AsyncMock()
    session.flush = AsyncMock()

    repository = BlacklistedGuildRepository(session)

    await repository.delete(entry)

    session.delete.assert_awaited_once_with(entry)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_verification_log_repository_add() -> None:
    """Adding a verification log should add and flush it."""

    verification_log = MagicMock(spec=VerificationLog)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = VerificationLogRepository(session)

    result = await repository.add(verification_log)

    assert result is verification_log
    session.add.assert_called_once_with(verification_log)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_verification_log_repository_list_recent_by_guild() -> None:
    """Recent verification logs should be returned for a guild."""

    guild_id = uuid4()
    verification_log = MagicMock(spec=VerificationLog)

    scalars = MagicMock()
    scalars.all.return_value = [verification_log]

    result_proxy = MagicMock()
    result_proxy.scalars.return_value = scalars

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_proxy)

    repository = VerificationLogRepository(session)

    result = await repository.list_recent_by_guild(
        guild_id=guild_id,
        limit=50,
    )

    assert result == [verification_log]
    session.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_verification_log_repository_lists_shared_ip_users() -> None:
    """Users sharing an IP hash should be returned without duplicates."""

    guild_id = uuid4()

    scalars = MagicMock()
    scalars.all.return_value = [
        "123456789012345678",
        "987654321098765432",
    ]

    result_proxy = MagicMock()
    result_proxy.scalars.return_value = scalars

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_proxy)

    repository = VerificationLogRepository(session)

    result = await repository.list_user_ids_by_ip_hash(
        guild_id=guild_id,
        ip_hash="a" * 64,
    )

    assert result == [
        "123456789012345678",
        "987654321098765432",
    ]
    session.execute.assert_awaited_once()
