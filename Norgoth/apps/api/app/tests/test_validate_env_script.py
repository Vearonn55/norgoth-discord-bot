"""Tests for Norgoth/scripts/docker/validate_env.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[4] / "scripts" / "docker" / "validate_env.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("norbot_validate_env", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_env_accepts_complete_oauth_and_token(tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "DISCORD_BOT_TOKEN=bot-token\n"
        "NORGOTH_DISCORD_CLIENT_ID=123\n"
        "NORGOTH_DISCORD_CLIENT_SECRET=secret\n"
        "NORGOTH_DISCORD_REDIRECT_URI=https://api.test.norbot.io/callback\n",
        encoding="utf-8",
    )
    errors = _load().validate_env_file("test", env_file)
    assert errors == []


def test_validate_env_rejects_redirect_without_client(tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "DISCORD_BOT_TOKEN=bot-token\n"
        "NORGOTH_DISCORD_CLIENT_ID=\n"
        "NORGOTH_DISCORD_CLIENT_SECRET=\n"
        "NORGOTH_DISCORD_REDIRECT_URI="
        "https://api.test.norbot.io/api/v1/oauth/discord/callback\n",
        encoding="utf-8",
    )
    errors = _load().validate_env_file("test", env_file)
    joined = "\n".join(errors)
    assert "all-or-none" in joined
    assert "NORGOTH_DISCORD_REDIRECT_URI: set" in joined
    assert "https://" not in joined
    assert "bot-token" not in joined


def test_validate_env_rejects_missing_bot_token(tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "DISCORD_BOT_TOKEN=\n"
        "NORGOTH_DISCORD_CLIENT_ID=123\n"
        "NORGOTH_DISCORD_CLIENT_SECRET=secret\n"
        "NORGOTH_DISCORD_REDIRECT_URI=https://api.test.norbot.io/callback\n",
        encoding="utf-8",
    )
    errors = _load().validate_env_file("test", env_file)
    joined = "\n".join(errors)
    assert "DISCORD_BOT_TOKEN is empty" in joined
    assert "secret" not in joined


def test_validate_env_rejects_blank_oauth_on_vds(tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text("DISCORD_BOT_TOKEN=bot-token\n", encoding="utf-8")
    errors = _load().validate_env_file("test", env_file)
    assert any("Discord OAuth is blank" in line for line in errors)
