"""Tests for guild active ban registry."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.repositories.guild_active_ban_repository import GuildActiveBanRepository
from app.services.guild_ban_service import GuildBanService


@pytest.mark.anyio
async def test_upsert_active_ban_creates_row() -> None:
    guild_id = uuid4()
    repo = AsyncMock(spec=GuildActiveBanRepository)
    repo.upsert_active_ban.return_value = object()

    guild_repo = AsyncMock()
    guild_repo.get_by_discord_guild_id.return_value = type(
        "Guild",
        (),
        {"id": guild_id},
    )()

    service = GuildBanService(
        guild_repository=guild_repo,
        ban_repository=repo,
    )

    await service.upsert_active_ban(
        discord_guild_id="111111111111111111",
        discord_user_id="222222222222222222",
        username_snapshot="banned_user",
        display_name_snapshot="Banned",
        source="gateway_ban",
        banned_at=datetime.now(timezone.utc),
    )

    repo.upsert_active_ban.assert_awaited_once()
    assert repo.upsert_active_ban.await_args.kwargs["guild_id"] == guild_id


@pytest.mark.anyio
async def test_deactivate_ban_is_idempotent_when_missing() -> None:
    repo = AsyncMock(spec=GuildActiveBanRepository)
    repo.deactivate_ban.return_value = None
    guild_repo = AsyncMock()
    guild_repo.get_by_discord_guild_id.return_value = type(
        "Guild",
        (),
        {"id": uuid4()},
    )()

    service = GuildBanService(
        guild_repository=guild_repo,
        ban_repository=repo,
    )

    result = await service.deactivate_ban(
        discord_guild_id="111111111111111111",
        discord_user_id="222222222222222222",
    )

    assert result is None
