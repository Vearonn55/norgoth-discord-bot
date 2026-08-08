"""Tests for guild and configuration business services."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.configuration import Configuration
from app.models.discord_guild import DiscordGuild
from app.repositories.configuration_repository import (
    ConfigurationRepository,
)
from app.repositories.discord_guild_repository import (
    DiscordGuildRepository,
)
from app.services.configuration_service import (
    ConfigurationService,
)
from app.services.guild_service import GuildService


@pytest.mark.anyio
async def test_register_or_update_creates_missing_guild() -> None:
    """A missing guild should be registered."""

    repository = AsyncMock(spec=DiscordGuildRepository)
    repository.get_by_discord_guild_id.return_value = None
    repository.add.side_effect = lambda guild: guild

    service = GuildService(repository)

    result = await service.register_or_update(
        discord_guild_id="123456789012345678",
        discord_guild_name="Norgoth Community",
        discord_owner_id="987654321098765432",
    )

    assert result.discord_guild_id == "123456789012345678"
    assert result.discord_guild_name == "Norgoth Community"
    assert result.discord_owner_id == "987654321098765432"
    repository.add.assert_awaited_once_with(result)
    repository.save.assert_not_awaited()


@pytest.mark.anyio
async def test_register_or_update_updates_existing_guild() -> None:
    """An existing guild should receive current Discord metadata."""

    guild = DiscordGuild(
        discord_guild_id="123456789012345678",
        discord_guild_name="Old Name",
        discord_owner_id="111111111111111111",
    )

    repository = AsyncMock(spec=DiscordGuildRepository)
    repository.get_by_discord_guild_id.return_value = guild
    repository.save.side_effect = lambda saved_guild: saved_guild

    service = GuildService(repository)

    result = await service.register_or_update(
        discord_guild_id="123456789012345678",
        discord_guild_name="New Name",
        discord_owner_id="987654321098765432",
    )

    assert result is guild
    assert guild.discord_guild_name == "New Name"
    assert guild.discord_owner_id == "987654321098765432"
    repository.save.assert_awaited_once_with(guild)
    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_remove_returns_false_when_guild_is_missing() -> None:
    """Removing an unknown guild should report no change."""

    repository = AsyncMock(spec=DiscordGuildRepository)
    repository.get_by_discord_guild_id.return_value = None

    service = GuildService(repository)

    result = await service.remove("123456789012345678")

    assert result is False
    repository.delete.assert_not_awaited()


@pytest.mark.anyio
async def test_remove_deletes_existing_guild() -> None:
    """Removing a known guild should delete it."""

    guild = DiscordGuild(
        discord_guild_id="123456789012345678",
        discord_guild_name="Norgoth Community",
        discord_owner_id="987654321098765432",
    )

    repository = AsyncMock(spec=DiscordGuildRepository)
    repository.get_by_discord_guild_id.return_value = guild

    service = GuildService(repository)

    result = await service.remove("123456789012345678")

    assert result is True
    repository.delete.assert_awaited_once_with(guild)


@pytest.mark.anyio
async def test_create_or_update_creates_missing_configuration() -> None:
    """A guild without settings should receive a configuration."""

    guild_id = uuid4()

    repository = AsyncMock(spec=ConfigurationRepository)
    repository.get_by_guild_id.return_value = None
    repository.add.side_effect = lambda configuration: configuration

    service = ConfigurationService(repository)

    result = await service.create_or_update(
        guild_id=guild_id,
        verification_channel_id="111111111111111111",
        log_channel_id="222222222222222222",
        verified_role_id="333333333333333333",
        unverified_role_id="444444444444444444",
        member_role_id="555555555555555555",
        minimum_account_age_days=30,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        enabled=True,
    )

    assert result.guild_id == guild_id
    assert result.verification_channel_id == "111111111111111111"
    assert result.log_channel_id == "222222222222222222"
    assert result.minimum_account_age_days == 30
    assert result.deny_vpn_or_proxy is True
    repository.add.assert_awaited_once_with(result)
    repository.save.assert_not_awaited()


@pytest.mark.anyio
async def test_create_or_update_updates_existing_configuration() -> None:
    """Existing guild settings should be updated in place."""

    guild_id = uuid4()
    configuration = Configuration(
        guild_id=guild_id,
        verification_channel_id="111111111111111111",
        log_channel_id="222222222222222222",
        verified_role_id="333333333333333333",
        unverified_role_id="444444444444444444",
        member_role_id="555555555555555555",
        minimum_account_age_days=0,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        enabled=True,
    )

    repository = AsyncMock(spec=ConfigurationRepository)
    repository.get_by_guild_id.return_value = configuration
    repository.save.side_effect = lambda saved_configuration: saved_configuration

    service = ConfigurationService(repository)

    result = await service.create_or_update(
        guild_id=guild_id,
        verification_channel_id="666666666666666666",
        log_channel_id="777777777777777777",
        verified_role_id="888888888888888888",
        unverified_role_id="999999999999999999",
        member_role_id="101010101010101010",
        minimum_account_age_days=14,
        session_timeout_seconds=600,
        deny_vpn_or_proxy=False,
        deny_shared_ip=False,
        enabled=False,
    )

    assert result is configuration
    assert configuration.verification_channel_id == "666666666666666666"
    assert configuration.log_channel_id == "777777777777777777"
    assert configuration.minimum_account_age_days == 14
    assert configuration.session_timeout_seconds == 600
    assert configuration.deny_vpn_or_proxy is False
    assert configuration.deny_shared_ip is False
    assert configuration.enabled is False
    repository.save.assert_awaited_once_with(configuration)
    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_set_enabled_returns_none_when_configuration_is_missing() -> None:
    """An unknown configuration should not be updated."""

    guild_id = uuid4()

    repository = AsyncMock(spec=ConfigurationRepository)
    repository.get_by_guild_id.return_value = None

    service = ConfigurationService(repository)

    result = await service.set_enabled(
        guild_id=guild_id,
        enabled=True,
    )

    assert result is None
    repository.save.assert_not_awaited()


@pytest.mark.anyio
async def test_set_enabled_updates_existing_configuration() -> None:
    """A known configuration should be enabled or disabled."""

    guild_id = uuid4()
    configuration = Configuration(
        guild_id=guild_id,
        verification_channel_id="111111111111111111",
        log_channel_id="222222222222222222",
        verified_role_id="333333333333333333",
        unverified_role_id="444444444444444444",
        member_role_id="555555555555555555",
        minimum_account_age_days=30,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        enabled=True,
    )

    repository = AsyncMock(spec=ConfigurationRepository)
    repository.get_by_guild_id.return_value = configuration
    repository.save.side_effect = lambda saved_configuration: saved_configuration

    service = ConfigurationService(repository)

    result = await service.set_enabled(
        guild_id=guild_id,
        enabled=False,
    )

    assert result is configuration
    assert configuration.enabled is False
    repository.save.assert_awaited_once_with(configuration)
