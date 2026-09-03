"""Sync-mode and command permission decorator smoke tests."""

from __future__ import annotations

from bot.commands.checks import module_enabled, truncate_reason
from bot.commands.errors import ModuleDisabledError
from bot.config import BotSettings


def test_truncate_reason() -> None:
    assert truncate_reason(None) is None
    assert truncate_reason("  hi  ") == "hi"
    long = "x" * 500
    assert truncate_reason(long, limit=10) == "xxxxxxxxx…"


def test_module_enabled_decorator_factory() -> None:
    check = module_enabled("moderation")
    assert callable(check)


def test_bot_settings_sync_mode_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.delenv("NORBOT_COMMAND_SYNC_MODE", raising=False)
    monkeypatch.delenv("NORBOT_TEST_GUILD_IDS", raising=False)
    settings = BotSettings.from_environment()
    assert settings.command_sync_mode == "guild"
    assert settings.test_guild_ids == ()


def test_bot_settings_parses_test_guilds(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setenv("NORBOT_COMMAND_SYNC_MODE", "global")
    monkeypatch.setenv("NORBOT_TEST_GUILD_IDS", "111, 222;333")
    settings = BotSettings.from_environment()
    assert settings.command_sync_mode == "global"
    assert settings.test_guild_ids == (111, 222, 333)


def test_module_disabled_error_message() -> None:
    err = ModuleDisabledError("leveling")
    assert err.module == "leveling"
    assert "leveling" in str(err)
