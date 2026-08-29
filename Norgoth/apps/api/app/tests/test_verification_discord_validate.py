"""Tests for Discord resource validation helper."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.models.enums import RiskAction
from app.services.verification_discord_validate import (
    validate_verification_discord_resources,
)
from app.services.views import ConfigurationView


def _config() -> ConfigurationView:
    return ConfigurationView(
        id=uuid4(),
        guild_id=uuid4(),
        verification_channel_id="100",
        log_channel_id="101",
        unverified_role_id="200",
        member_role_id="201",
        manual_review_role_id="",
        minimum_account_age_days=0,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        vpn_or_proxy_action=RiskAction.DENY,
        shared_ip_action=RiskAction.DENY,
        enabled=True,
        panel_message_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_rejects_channel_from_other_guild() -> None:
    bot = AsyncMock()
    bot.list_guild_roles.return_value = [
        {"id": "99", "permissions": str(1 << 28), "position": 0},
        {"id": "bot-role", "permissions": str(1 << 28), "position": 10},
        {"id": "200", "permissions": "0", "position": 1, "managed": False},
        {"id": "201", "permissions": "0", "position": 2, "managed": False},
    ]
    bot.get_bot_user.return_value = {"id": "bot-user"}
    bot.get_guild_member.return_value = {"roles": ["bot-role"]}
    bot.get_channel.side_effect = [
        {"id": "100", "guild_id": "other", "permission_overwrites": []},
        {"id": "101", "guild_id": "99", "permission_overwrites": []},
    ]

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(),
    )
    assert result.ok is False
    assert any(issue.code == "discord_resource_not_in_guild" for issue in result.issues)


@pytest.mark.asyncio
async def test_missing_channel_is_degraded() -> None:
    bot = AsyncMock()
    bot.list_guild_roles.return_value = [
        {"id": "99", "permissions": str(1 << 3), "position": 0},
        {"id": "bot-role", "permissions": str(1 << 3), "position": 10},
        {"id": "200", "permissions": "0", "position": 1, "managed": False},
        {"id": "201", "permissions": "0", "position": 2, "managed": False},
    ]
    bot.get_bot_user.return_value = {"id": "bot-user"}
    bot.get_guild_member.return_value = {"roles": ["bot-role"]}
    bot.get_channel.side_effect = DiscordBotAPIError("missing", status_code=404)

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(),
    )
    assert result.ok is False
    assert result.setup_state == "degraded"


@pytest.mark.asyncio
async def test_bot_not_installed_when_member_missing() -> None:
    bot = AsyncMock()
    bot.list_guild_roles.return_value = []
    bot.get_bot_user.return_value = {"id": "bot-user"}
    bot.get_guild_member.side_effect = DiscordBotAPIError("missing", status_code=404)

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(),
    )
    assert result.ok is False
    assert any(issue.code == "bot_not_installed" for issue in result.issues)


@pytest.mark.asyncio
async def test_managed_role_uses_role_managed_code() -> None:
    bot = AsyncMock()
    bot.list_guild_roles.return_value = [
        {"id": "99", "permissions": str(1 << 28), "position": 0},
        {"id": "bot-role", "permissions": str(1 << 28), "position": 10},
        {"id": "200", "permissions": "0", "position": 1, "managed": True},
        {"id": "201", "permissions": "0", "position": 2, "managed": False},
    ]
    bot.get_bot_user.return_value = {"id": "bot-user"}
    bot.get_guild_member.return_value = {"roles": ["bot-role"]}
    bot.get_channel.return_value = {
        "id": "100",
        "guild_id": "99",
        "permission_overwrites": [],
    }

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(),
    )
    assert result.ok is False
    assert any(issue.code == "role_managed" for issue in result.issues)
