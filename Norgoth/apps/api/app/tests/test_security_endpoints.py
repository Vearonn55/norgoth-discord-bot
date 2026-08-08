"""HTTP tests for user-list and blacklisted-guild endpoints."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_blacklisted_guild_service,
    get_guild_service,
    get_user_list_service,
)
from app.api.v1.router import api_router
from app.db.session import get_database_session
from app.models.blacklisted_guild import BlacklistedGuild
from app.models.discord_guild import DiscordGuild
from app.models.enums import UserListType
from app.models.user_list_entry import UserListEntry
from app.services.blacklisted_guild_service import (
    BlacklistedGuildService,
)
from app.services.guild_service import GuildService
from app.services.user_list_service import UserListService

DISCORD_GUILD_ID = "123456789012345678"
DISCORD_OWNER_ID = "987654321098765432"
DISCORD_USER_ID = "111111111111111111"
BLACKLISTED_DISCORD_GUILD_ID = "222222222222222222"


def _build_guild(
    *,
    guild_id: UUID | None = None,
) -> DiscordGuild:
    """Create a complete Discord guild fixture."""

    timestamp = datetime.now(UTC)

    return DiscordGuild(
        id=guild_id or uuid4(),
        discord_guild_id=DISCORD_GUILD_ID,
        discord_guild_name="Norgoth Community",
        discord_owner_id=DISCORD_OWNER_ID,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _build_user_list_entry(
    *,
    guild_id: UUID,
    list_type: UserListType = UserListType.BLACKLIST,
) -> UserListEntry:
    """Create a complete user-list fixture."""

    timestamp = datetime.now(UTC)

    return UserListEntry(
        id=uuid4(),
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        list_type=list_type,
        reason="Test reason",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _build_blacklisted_guild(
    *,
    guild_id: UUID,
) -> BlacklistedGuild:
    """Create a complete blacklisted-guild fixture."""

    timestamp = datetime.now(UTC)

    return BlacklistedGuild(
        id=uuid4(),
        guild_id=guild_id,
        blacklisted_discord_guild_id=BLACKLISTED_DISCORD_GUILD_ID,
        reason="Blocked community",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _mock_session() -> AsyncMock:
    """Create a mocked async database session."""

    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    return session


def _create_test_client(
    *,
    guild_service: GuildService,
    user_list_service: UserListService,
    blacklisted_guild_service: BlacklistedGuildService,
    session: AsyncSession,
) -> TestClient:
    """Create an application with overridden dependencies."""

    application = FastAPI()
    application.include_router(api_router)

    async def override_database_session() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_guild_service] = lambda: guild_service
    application.dependency_overrides[get_user_list_service] = lambda: user_list_service
    application.dependency_overrides[get_blacklisted_guild_service] = lambda: (
        blacklisted_guild_service
    )
    application.dependency_overrides[get_database_session] = override_database_session

    return TestClient(application)


def test_list_user_entries_returns_entries() -> None:
    """GET should return user-list entries for a guild."""

    guild = _build_guild()
    entry = _build_user_list_entry(guild_id=guild.id)

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)
    user_list_service.list_entries.return_value = [entry]

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.get(
        f"/guilds/{DISCORD_GUILD_ID}/user-list",
        params={"list_type": "blacklist"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["discord_user_id"] == DISCORD_USER_ID
    assert response.json()[0]["list_type"] == "blacklist"

    user_list_service.list_entries.assert_awaited_once_with(
        guild_id=guild.id,
        list_type=UserListType.BLACKLIST,
    )


def test_list_user_entries_returns_not_found_for_unknown_guild() -> None:
    """GET should return 404 when the guild is unknown."""

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = None

    user_list_service = AsyncMock(spec=UserListService)
    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}/user-list")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Discord guild not found.",
    }
    user_list_service.list_entries.assert_not_awaited()


def test_put_user_entry_creates_or_updates_entry() -> None:
    """PUT should persist a whitelist or blacklist entry."""

    guild = _build_guild()
    entry = _build_user_list_entry(
        guild_id=guild.id,
        list_type=UserListType.WHITELIST,
    )

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)
    user_list_service.set_entry.return_value = entry

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.put(
        f"/guilds/{DISCORD_GUILD_ID}/user-list/{DISCORD_USER_ID}",
        json={
            "list_type": "whitelist",
            "reason": "Trusted member",
        },
    )

    assert response.status_code == 200
    assert response.json()["discord_user_id"] == DISCORD_USER_ID
    assert response.json()["list_type"] == "whitelist"

    user_list_service.set_entry.assert_awaited_once_with(
        guild_id=guild.id,
        discord_user_id=DISCORD_USER_ID,
        list_type=UserListType.WHITELIST,
        reason="Trusted member",
    )
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(entry)


def test_delete_user_entry_removes_entry() -> None:
    """DELETE should remove an existing user-list entry."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)
    user_list_service.remove_entry.return_value = True

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.delete(f"/guilds/{DISCORD_GUILD_ID}/user-list/{DISCORD_USER_ID}")

    assert response.status_code == 204
    assert response.content == b""

    user_list_service.remove_entry.assert_awaited_once_with(
        guild_id=guild.id,
        discord_user_id=DISCORD_USER_ID,
    )
    session.commit.assert_awaited_once_with()


def test_delete_user_entry_returns_not_found_when_missing() -> None:
    """DELETE should return 404 when the user entry is missing."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)
    user_list_service.remove_entry.return_value = False

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.delete(f"/guilds/{DISCORD_GUILD_ID}/user-list/{DISCORD_USER_ID}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "User list entry not found.",
    }
    session.commit.assert_not_awaited()


def test_list_blacklisted_guilds_returns_entries() -> None:
    """GET should return blacklisted guild entries."""

    guild = _build_guild()
    entry = _build_blacklisted_guild(guild_id=guild.id)

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    blacklisted_guild_service.list_entries.return_value = [entry]

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}/blacklisted-guilds")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["blacklisted_discord_guild_id"] == BLACKLISTED_DISCORD_GUILD_ID

    blacklisted_guild_service.list_entries.assert_awaited_once_with(guild.id)


def test_put_blacklisted_guild_creates_or_updates_entry() -> None:
    """PUT should persist a blacklisted Discord guild."""

    guild = _build_guild()
    entry = _build_blacklisted_guild(guild_id=guild.id)

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    blacklisted_guild_service.set_entry.return_value = entry

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.put(
        (f"/guilds/{DISCORD_GUILD_ID}/blacklisted-guilds/{BLACKLISTED_DISCORD_GUILD_ID}"),
        json={"reason": "Blocked community"},
    )

    assert response.status_code == 200
    assert response.json()["blacklisted_discord_guild_id"] == BLACKLISTED_DISCORD_GUILD_ID

    blacklisted_guild_service.set_entry.assert_awaited_once_with(
        guild_id=guild.id,
        blacklisted_discord_guild_id=(BLACKLISTED_DISCORD_GUILD_ID),
        reason="Blocked community",
    )
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(entry)


def test_delete_blacklisted_guild_removes_entry() -> None:
    """DELETE should remove a blacklisted Discord guild."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    blacklisted_guild_service.remove_entry.return_value = True

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.delete(
        f"/guilds/{DISCORD_GUILD_ID}/blacklisted-guilds/{BLACKLISTED_DISCORD_GUILD_ID}"
    )

    assert response.status_code == 204
    assert response.content == b""

    blacklisted_guild_service.remove_entry.assert_awaited_once_with(
        guild_id=guild.id,
        blacklisted_discord_guild_id=(BLACKLISTED_DISCORD_GUILD_ID),
    )
    session.commit.assert_awaited_once_with()


def test_invalid_user_list_type_returns_validation_error() -> None:
    """Unknown user-list types should be rejected."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    user_list_service = AsyncMock(spec=UserListService)
    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        session=session,
    )

    response = client.get(
        f"/guilds/{DISCORD_GUILD_ID}/user-list",
        params={"list_type": "unknown"},
    )

    assert response.status_code == 422
    user_list_service.list_entries.assert_not_awaited()
