"""HTTP tests for guild and configuration endpoints."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_configuration_service,
    get_guild_service,
)
from app.api.v1.router import api_router
from app.db.session import get_database_session
from app.models.configuration import Configuration
from app.models.discord_guild import DiscordGuild
from app.services.configuration_service import (
    ConfigurationService,
)
from app.services.guild_service import GuildService

DISCORD_GUILD_ID = "123456789012345678"
DISCORD_OWNER_ID = "987654321098765432"
VERIFICATION_CHANNEL_ID = "111111111111111111"
LOG_CHANNEL_ID = "222222222222222222"
VERIFIED_ROLE_ID = "333333333333333333"
UNVERIFIED_ROLE_ID = "444444444444444444"
MEMBER_ROLE_ID = "555555555555555555"


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


def _build_configuration(
    *,
    guild_id: UUID,
    enabled: bool = True,
) -> Configuration:
    """Create a complete guild configuration fixture."""

    timestamp = datetime.now(UTC)

    return Configuration(
        id=uuid4(),
        guild_id=guild_id,
        verification_channel_id=VERIFICATION_CHANNEL_ID,
        log_channel_id=LOG_CHANNEL_ID,
        verified_role_id=VERIFIED_ROLE_ID,
        unverified_role_id=UNVERIFIED_ROLE_ID,
        member_role_id=MEMBER_ROLE_ID,
        minimum_account_age_days=30,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        enabled=enabled,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _create_test_client(
    *,
    guild_service: GuildService,
    configuration_service: ConfigurationService,
    session: AsyncSession,
) -> TestClient:
    """Create an application with overridden API dependencies."""

    application = FastAPI()
    application.include_router(api_router)

    async def override_database_session() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_guild_service] = lambda: guild_service
    application.dependency_overrides[get_configuration_service] = lambda: configuration_service
    application.dependency_overrides[get_database_session] = override_database_session

    return TestClient(application)


def _mock_session() -> AsyncMock:
    """Create a mocked async database session."""

    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    return session


def test_get_guild_returns_registered_guild() -> None:
    """GET should return a known Discord guild."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    configuration_service = AsyncMock(spec=ConfigurationService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(guild.id)
    assert response.json()["discord_guild_id"] == DISCORD_GUILD_ID
    assert response.json()["discord_guild_name"] == "Norgoth Community"
    assert response.json()["discord_owner_id"] == DISCORD_OWNER_ID

    guild_service.get_by_discord_guild_id.assert_awaited_once_with(DISCORD_GUILD_ID)


def test_get_guild_returns_not_found_for_unknown_guild() -> None:
    """GET should return 404 when the guild is not registered."""

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = None

    configuration_service = AsyncMock(spec=ConfigurationService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Discord guild not found.",
    }


def test_put_guild_registers_or_updates_guild() -> None:
    """PUT should persist current Discord guild metadata."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.register_or_update.return_value = guild

    configuration_service = AsyncMock(spec=ConfigurationService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.put(
        f"/guilds/{DISCORD_GUILD_ID}",
        json={
            "discord_guild_name": "Norgoth Community",
            "discord_owner_id": DISCORD_OWNER_ID,
        },
    )

    assert response.status_code == 200
    assert response.json()["discord_guild_id"] == DISCORD_GUILD_ID

    guild_service.register_or_update.assert_awaited_once_with(
        discord_guild_id=DISCORD_GUILD_ID,
        discord_guild_name="Norgoth Community",
        discord_owner_id=DISCORD_OWNER_ID,
    )
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(guild)


def test_delete_guild_removes_registered_guild() -> None:
    """DELETE should remove a registered Discord guild."""

    guild_service = AsyncMock(spec=GuildService)
    guild_service.remove.return_value = True

    configuration_service = AsyncMock(spec=ConfigurationService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.delete(f"/guilds/{DISCORD_GUILD_ID}")

    assert response.status_code == 204
    assert response.content == b""

    guild_service.remove.assert_awaited_once_with(DISCORD_GUILD_ID)
    session.commit.assert_awaited_once_with()


def test_delete_guild_returns_not_found_for_unknown_guild() -> None:
    """DELETE should return 404 when the guild does not exist."""

    guild_service = AsyncMock(spec=GuildService)
    guild_service.remove.return_value = False

    configuration_service = AsyncMock(spec=ConfigurationService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.delete(f"/guilds/{DISCORD_GUILD_ID}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Discord guild not found.",
    }
    session.commit.assert_not_awaited()


def test_get_configuration_returns_guild_configuration() -> None:
    """GET should return settings for a registered guild."""

    guild = _build_guild()
    configuration = _build_configuration(guild_id=guild.id)

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    configuration_service = AsyncMock(spec=ConfigurationService)
    configuration_service.get_by_guild_id.return_value = configuration

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}/configuration")

    assert response.status_code == 200
    assert response.json()["guild_id"] == str(guild.id)
    assert response.json()["verification_channel_id"] == VERIFICATION_CHANNEL_ID
    assert response.json()["deny_vpn_or_proxy"] is True
    assert response.json()["deny_shared_ip"] is True


def test_get_configuration_returns_not_found_when_missing() -> None:
    """GET should return 404 when a guild has no configuration."""

    guild = _build_guild()

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    configuration_service = AsyncMock(spec=ConfigurationService)
    configuration_service.get_by_guild_id.return_value = None

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}/configuration")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Guild configuration not found.",
    }


def test_put_configuration_creates_or_updates_configuration() -> None:
    """PUT should persist verification settings for a guild."""

    guild = _build_guild()
    configuration = _build_configuration(guild_id=guild.id)

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    configuration_service = AsyncMock(spec=ConfigurationService)
    configuration_service.create_or_update.return_value = configuration

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.put(
        f"/guilds/{DISCORD_GUILD_ID}/configuration",
        json={
            "verification_channel_id": VERIFICATION_CHANNEL_ID,
            "log_channel_id": LOG_CHANNEL_ID,
            "verified_role_id": VERIFIED_ROLE_ID,
            "unverified_role_id": UNVERIFIED_ROLE_ID,
            "member_role_id": MEMBER_ROLE_ID,
            "minimum_account_age_days": 30,
            "session_timeout_seconds": 900,
            "deny_vpn_or_proxy": True,
            "deny_shared_ip": True,
            "enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is True

    configuration_service.create_or_update.assert_awaited_once_with(
        guild_id=guild.id,
        verification_channel_id=VERIFICATION_CHANNEL_ID,
        log_channel_id=LOG_CHANNEL_ID,
        verified_role_id=VERIFIED_ROLE_ID,
        unverified_role_id=UNVERIFIED_ROLE_ID,
        member_role_id=MEMBER_ROLE_ID,
        minimum_account_age_days=30,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        enabled=True,
    )
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(configuration)


def test_patch_configuration_enabled_updates_state() -> None:
    """PATCH should enable or disable an existing configuration."""

    guild = _build_guild()
    configuration = _build_configuration(
        guild_id=guild.id,
        enabled=False,
    )

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    configuration_service = AsyncMock(spec=ConfigurationService)
    configuration_service.set_enabled.return_value = configuration

    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.patch(
        f"/guilds/{DISCORD_GUILD_ID}/configuration/enabled",
        json={"enabled": False},
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is False

    configuration_service.set_enabled.assert_awaited_once_with(
        guild_id=guild.id,
        enabled=False,
    )
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(configuration)


def test_invalid_discord_guild_id_returns_validation_error() -> None:
    """Malformed guild snowflakes should be rejected by the API."""

    guild_service = AsyncMock(spec=GuildService)
    configuration_service = AsyncMock(spec=ConfigurationService)
    session = _mock_session()

    client = _create_test_client(
        guild_service=guild_service,
        configuration_service=configuration_service,
        session=session,
    )

    response = client.get("/guilds/not-a-snowflake")

    assert response.status_code == 422
    guild_service.get_by_discord_guild_id.assert_not_awaited()
