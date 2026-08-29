"""Tests for OAuth-backed high-risk guild membership resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.integrations.discord.oauth import DiscordOAuthClient, DiscordOAuthError
from app.services.verification_guild_membership import (
    resolve_high_risk_membership,
    resolve_matched_high_risk_guilds_from_user_guilds,
)


def test_resolve_matched_high_risk_guilds_from_user_guilds_matches_exact_ids() -> None:
    matched = resolve_matched_high_risk_guilds_from_user_guilds(
        user_guild_ids=frozenset(
            {"900000000000000001", "900000000000000099", "900000000000000002"}
        ),
        high_risk_guild_ids=frozenset(
            {"900000000000000001", "900000000000000002", "900000000000000003"}
        ),
    )

    assert matched == ("900000000000000001", "900000000000000002")


def test_resolve_matched_high_risk_guilds_from_user_guilds_rejects_substrings() -> None:
    matched = resolve_matched_high_risk_guilds_from_user_guilds(
        user_guild_ids=frozenset({"900000000000000001"}),
        high_risk_guild_ids=frozenset({"90000000000000000"}),
    )

    assert matched == ()


@pytest.mark.anyio
async def test_resolve_high_risk_membership_uses_oauth_guild_intersection() -> None:
    oauth_client = AsyncMock(spec=DiscordOAuthClient)
    oauth_client.get_current_user_guild_ids.return_value = frozenset(
        {"900000000000000001", "900000000000000099"}
    )

    result = await resolve_high_risk_membership(
        oauth_client,
        access_token="token",
        token_scopes=frozenset({"identify", "guilds"}),
        high_risk_guild_ids=frozenset(
            {"900000000000000001", "900000000000000002"}
        ),
    )

    assert result.matched_high_risk_guild_ids == ("900000000000000001",)
    assert result.membership_check_unavailable is False


@pytest.mark.anyio
async def test_resolve_high_risk_membership_without_guilds_scope_is_unavailable() -> None:
    oauth_client = AsyncMock(spec=DiscordOAuthClient)

    result = await resolve_high_risk_membership(
        oauth_client,
        access_token="token",
        token_scopes=frozenset({"identify"}),
        high_risk_guild_ids=frozenset({"900000000000000001"}),
    )

    assert result.matched_high_risk_guild_ids == ()
    assert result.membership_check_unavailable is True
    oauth_client.get_current_user_guild_ids.assert_not_called()


@pytest.mark.anyio
async def test_resolve_high_risk_membership_oauth_failure_is_unavailable() -> None:
    oauth_client = AsyncMock(spec=DiscordOAuthClient)
    oauth_client.get_current_user_guild_ids.side_effect = DiscordOAuthError(
        "limited",
        http_status=429,
        operation="current_user_guilds",
    )

    result = await resolve_high_risk_membership(
        oauth_client,
        access_token="token",
        token_scopes=frozenset({"identify", "guilds"}),
        high_risk_guild_ids=frozenset({"900000000000000001"}),
    )

    assert result.matched_high_risk_guild_ids == ()
    assert result.membership_check_unavailable is True


@pytest.mark.anyio
async def test_resolve_high_risk_membership_skips_fetch_when_no_configured_ids() -> None:
    oauth_client = AsyncMock(spec=DiscordOAuthClient)

    result = await resolve_high_risk_membership(
        oauth_client,
        access_token="token",
        token_scopes=frozenset({"identify"}),
        high_risk_guild_ids=frozenset(),
    )

    assert result.matched_high_risk_guild_ids == ()
    assert result.membership_check_unavailable is False
    oauth_client.get_current_user_guild_ids.assert_not_called()
