"""Tests for Discord resource validation helper."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.security.discord_permissions import EMBED_LINKS, SEND_MESSAGES, VIEW_CHANNEL
from app.models.enums import RiskAction
from app.services.verification_discord_validate import (
    validate_verification_discord_resources,
)
from app.services.views import ConfigurationView


def _config(**overrides: object) -> ConfigurationView:
    base = {
        "id": uuid4(),
        "guild_id": uuid4(),
        "verification_channel_id": "100",
        "log_channel_id": "101",
        "unverified_role_id": "200",
        "member_role_id": "201",
        "manual_review_role_id": "",
        "minimum_account_age_days": 0,
        "session_timeout_seconds": 900,
        "deny_vpn_or_proxy": True,
        "deny_shared_ip": True,
        "vpn_or_proxy_action": RiskAction.DENY,
        "shared_ip_action": RiskAction.DENY,
        "enabled": True,
        "panel_message_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return ConfigurationView(**base)


def _healthy_bot(
    *,
    channel_overwrites: list[dict[str, object]] | None = None,
    category_overwrites: list[dict[str, object]] | None = None,
    parent_id: str | None = "300",
) -> AsyncMock:
    bot = AsyncMock()
    bot.list_guild_roles.return_value = [
        {
            "id": "99",
            "permissions": str(VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS | (1 << 28)),
            "position": 0,
        },
        {
            "id": "bot-role",
            "permissions": str(VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS | (1 << 28)),
            "position": 10,
        },
        {"id": "200", "permissions": "0", "position": 1, "managed": False},
        {"id": "201", "permissions": "0", "position": 2, "managed": False},
    ]
    bot.get_bot_user.return_value = {"id": "bot-user"}
    bot.get_guild_member.return_value = {"roles": ["bot-role"]}

    async def _get_channel(channel_id: str) -> dict[str, object]:
        if channel_id == "300":
            return {
                "id": "300",
                "guild_id": "99",
                "type": 4,
                "permission_overwrites": category_overwrites or [],
            }
        return {
            "id": channel_id,
            "guild_id": "99",
            "type": 0,
            "name": "verification",
            "parent_id": parent_id,
            "permission_overwrites": channel_overwrites or [],
        }

    bot.get_channel.side_effect = _get_channel
    return bot


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
        {"id": "100", "guild_id": "other", "type": 0, "permission_overwrites": []},
        {"id": "101", "guild_id": "99", "type": 0, "permission_overwrites": []},
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
    bot = _healthy_bot(parent_id=None)
    bot.list_guild_roles.return_value = [
        {"id": "99", "permissions": str(1 << 28), "position": 0},
        {"id": "bot-role", "permissions": str(1 << 28), "position": 10},
        {"id": "200", "permissions": "0", "position": 1, "managed": True},
        {"id": "201", "permissions": "0", "position": 2, "managed": False},
    ]

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(log_channel_id=""),
    )
    assert result.ok is False
    assert any(issue.code == "role_managed" for issue in result.issues)


@pytest.mark.asyncio
async def test_category_inheritance_allows_save_when_channel_overwrite_fixes_category() -> None:
    bot = _healthy_bot(
        parent_id="300",
        category_overwrites=[
            {"id": "99", "allow": "0", "deny": str(VIEW_CHANNEL)},
        ],
        channel_overwrites=[
            {"id": "bot-role", "allow": str(VIEW_CHANNEL), "deny": "0"},
        ],
    )

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(log_channel_id=""),
    )
    assert result.ok is True


@pytest.mark.asyncio
async def test_structured_missing_channel_permissions_issue() -> None:
    bot = _healthy_bot(
        parent_id="300",
        category_overwrites=[
            {"id": "99", "allow": "0", "deny": str(SEND_MESSAGES)},
        ],
    )

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(log_channel_id=""),
    )
    assert result.ok is False
    issue = next(
        issue for issue in result.issues if issue.code == "missing_channel_permissions"
    )
    assert issue.channel_name == "verification"
    assert issue.missing_permissions == ["Send Messages"]
    assert issue.overwrite_scope == "category"


@pytest.mark.asyncio
async def test_read_message_history_not_required() -> None:
    bot = _healthy_bot(
        parent_id=None,
        channel_overwrites=[
            {"id": "99", "allow": "0", "deny": str(1 << 16)},
        ],
    )

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(log_channel_id=""),
    )
    assert result.ok is True


@pytest.mark.asyncio
async def test_unsupported_channel_type() -> None:
    bot = _healthy_bot(parent_id=None)
    bot.get_channel.side_effect = [
        {
            "id": "100",
            "guild_id": "99",
            "type": 2,
            "name": "voice",
            "permission_overwrites": [],
        }
    ]

    result = await validate_verification_discord_resources(
        bot_client=bot,
        discord_guild_id="99",
        configuration=_config(log_channel_id=""),
    )
    assert result.ok is False
    assert any(
        issue.code == "unsupported_verification_channel_type" for issue in result.issues
    )
