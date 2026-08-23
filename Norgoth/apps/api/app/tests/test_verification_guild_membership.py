"""Tests for bot-backed high-risk guild membership resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.services.verification_guild_membership import resolve_matched_high_risk_guilds


@pytest.mark.anyio
async def test_resolve_matched_high_risk_guilds_returns_members() -> None:
    bot_client = AsyncMock()
    bot_client.get_guild_member.side_effect = [
        {"user": {"id": "123"}},
        DiscordBotAPIError("missing", status_code=404),
    ]

    matched = await resolve_matched_high_risk_guilds(
        bot_client,
        user_id="123",
        high_risk_guild_ids=frozenset(
            {"900000000000000001", "900000000000000002"}
        ),
    )

    assert matched == ("900000000000000001",)


@pytest.mark.anyio
async def test_resolve_matched_high_risk_guilds_skips_inaccessible_guilds() -> None:
    bot_client = AsyncMock()
    bot_client.get_guild_member.side_effect = DiscordBotAPIError(
        "forbidden",
        status_code=403,
    )

    matched = await resolve_matched_high_risk_guilds(
        bot_client,
        user_id="123",
        high_risk_guild_ids=frozenset({"900000000000000001"}),
    )

    assert matched == ()


@pytest.mark.anyio
async def test_resolve_matched_high_risk_guilds_without_bot() -> None:
    matched = await resolve_matched_high_risk_guilds(
        None,
        user_id="123",
        high_risk_guild_ids=frozenset({"900000000000000001"}),
    )

    assert matched == ()
