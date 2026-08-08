"""Tests for Discord guild and configuration repositories."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration
from app.models.discord_guild import DiscordGuild
from app.repositories.configuration_repository import (
    ConfigurationRepository,
)
from app.repositories.discord_guild_repository import (
    DiscordGuildRepository,
)


@pytest.mark.anyio
async def test_discord_guild_repository_get_by_id() -> None:
    """A guild should be retrievable by its internal UUID."""

    guild_id = uuid4()
    guild = MagicMock(spec=DiscordGuild)

    session = MagicMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=guild)

    repository = DiscordGuildRepository(session)

    result = await repository.get_by_id(guild_id)

    assert result is guild
    session.get.assert_awaited_once_with(DiscordGuild, guild_id)


@pytest.mark.anyio
async def test_discord_guild_repository_get_by_discord_id() -> None:
    """A guild should be retrievable by its Discord snowflake."""

    guild = MagicMock(spec=DiscordGuild)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = guild

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=scalar_result)

    repository = DiscordGuildRepository(session)

    result = await repository.get_by_discord_guild_id("123456789012345678")

    assert result is guild
    session.execute.assert_awaited_once()
    scalar_result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.anyio
async def test_discord_guild_repository_add() -> None:
    """Adding a guild should add and flush the entity."""

    guild = MagicMock(spec=DiscordGuild)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = DiscordGuildRepository(session)

    result = await repository.add(guild)

    assert result is guild
    session.add.assert_called_once_with(guild)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_discord_guild_repository_save() -> None:
    """Saving a guild should flush pending model changes."""

    guild = MagicMock(spec=DiscordGuild)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = DiscordGuildRepository(session)

    result = await repository.save(guild)

    assert result is guild
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_discord_guild_repository_delete() -> None:
    """Deleting a guild should delete and flush the entity."""

    guild = MagicMock(spec=DiscordGuild)

    session = MagicMock(spec=AsyncSession)
    session.delete = AsyncMock()
    session.flush = AsyncMock()

    repository = DiscordGuildRepository(session)

    await repository.delete(guild)

    session.delete.assert_awaited_once_with(guild)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_configuration_repository_get_by_id() -> None:
    """A configuration should be retrievable by its UUID."""

    configuration_id = uuid4()
    configuration = MagicMock(spec=Configuration)

    session = MagicMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=configuration)

    repository = ConfigurationRepository(session)

    result = await repository.get_by_id(configuration_id)

    assert result is configuration
    session.get.assert_awaited_once_with(
        Configuration,
        configuration_id,
    )


@pytest.mark.anyio
async def test_configuration_repository_get_by_guild_id() -> None:
    """A configuration should be retrievable by its guild UUID."""

    guild_id = uuid4()
    configuration = MagicMock(spec=Configuration)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = configuration

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=scalar_result)

    repository = ConfigurationRepository(session)

    result = await repository.get_by_guild_id(guild_id)

    assert result is configuration
    session.execute.assert_awaited_once()
    scalar_result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.anyio
async def test_configuration_repository_add() -> None:
    """Adding a configuration should add and flush the entity."""

    configuration = MagicMock(spec=Configuration)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = ConfigurationRepository(session)

    result = await repository.add(configuration)

    assert result is configuration
    session.add.assert_called_once_with(configuration)
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_configuration_repository_save() -> None:
    """Saving a configuration should flush pending model changes."""

    configuration = MagicMock(spec=Configuration)

    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()

    repository = ConfigurationRepository(session)

    result = await repository.save(configuration)

    assert result is configuration
    session.flush.assert_awaited_once_with()


@pytest.mark.anyio
async def test_configuration_repository_delete() -> None:
    """Deleting a configuration should delete and flush the entity."""

    configuration = MagicMock(spec=Configuration)

    session = MagicMock(spec=AsyncSession)
    session.delete = AsyncMock()
    session.flush = AsyncMock()

    repository = ConfigurationRepository(session)

    await repository.delete(configuration)

    session.delete.assert_awaited_once_with(configuration)
    session.flush.assert_awaited_once_with()
