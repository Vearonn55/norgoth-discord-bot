"""Tests for application configuration."""

import base64

import pytest
from pytest import MonkeyPatch

from app.core.config import Settings, get_settings


def _clear_ip_environment(monkeypatch: MonkeyPatch) -> None:
    """Remove IP protection settings from the test environment."""

    monkeypatch.delenv("NORGOTH_IP_HASH_KEY", raising=False)
    monkeypatch.delenv("NORGOTH_IP_ENCRYPTION_KEY", raising=False)


def _clear_discord_environment(monkeypatch: MonkeyPatch) -> None:
    """Remove Discord OAuth settings from the test environment."""

    monkeypatch.delenv("NORGOTH_DISCORD_CLIENT_ID", raising=False)
    monkeypatch.delenv(
        "NORGOTH_DISCORD_CLIENT_SECRET",
        raising=False,
    )
    monkeypatch.delenv(
        "NORGOTH_DISCORD_REDIRECT_URI",
        raising=False,
    )


def test_settings_do_not_require_database_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    """The API should start without configured database access."""

    monkeypatch.delenv("NORGOTH_DATABASE_URL", raising=False)
    monkeypatch.delenv("NORGOTH_DATABASE_ECHO", raising=False)
    _clear_ip_environment(monkeypatch)
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.database_url is None
    assert settings.database_echo is False

    get_settings.cache_clear()


def test_settings_read_database_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    """Database settings should be read from environment variables."""

    monkeypatch.setenv(
        "NORGOTH_DATABASE_URL",
        "postgresql://user:password@localhost:5432/norgoth",
    )
    monkeypatch.setenv("NORGOTH_DATABASE_ECHO", "true")
    _clear_ip_environment(monkeypatch)
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.database_url == ("postgresql://user:password@localhost:5432/norgoth")
    assert settings.database_echo is True

    get_settings.cache_clear()


def test_blank_database_url_is_treated_as_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    """Whitespace-only database URLs should not enable database access."""

    monkeypatch.setenv("NORGOTH_DATABASE_URL", "   ")
    _clear_ip_environment(monkeypatch)
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.database_url is None

    get_settings.cache_clear()


def test_ip_protection_keys_are_optional_together(
    monkeypatch: MonkeyPatch,
) -> None:
    """The API should start before IP protection is configured."""

    _clear_ip_environment(monkeypatch)
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.ip_hash_key is None
    assert settings.ip_encryption_key is None

    get_settings.cache_clear()


def test_settings_decode_ip_protection_keys(
    monkeypatch: MonkeyPatch,
) -> None:
    """Base64 IP protection keys should decode into bytes."""

    hash_key = b"h" * 32
    encryption_key = b"e" * 32

    monkeypatch.setenv(
        "NORGOTH_IP_HASH_KEY",
        base64.b64encode(hash_key).decode("ascii"),
    )
    monkeypatch.setenv(
        "NORGOTH_IP_ENCRYPTION_KEY",
        base64.b64encode(encryption_key).decode("ascii"),
    )
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.ip_hash_key == hash_key
    assert settings.ip_encryption_key == encryption_key

    get_settings.cache_clear()


@pytest.mark.parametrize(
    "environment_name",
    [
        "NORGOTH_IP_HASH_KEY",
        "NORGOTH_IP_ENCRYPTION_KEY",
    ],
)
def test_settings_reject_invalid_base64_ip_keys(
    monkeypatch: MonkeyPatch,
    environment_name: str,
) -> None:
    """Malformed Base64 security keys should be rejected."""

    valid_key = base64.b64encode(b"x" * 32).decode("ascii")

    monkeypatch.setenv("NORGOTH_IP_HASH_KEY", valid_key)
    monkeypatch.setenv("NORGOTH_IP_ENCRYPTION_KEY", valid_key)
    monkeypatch.setenv(environment_name, "not-valid-base64!")
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    with pytest.raises(
        ValueError,
        match="must contain valid Base64",
    ):
        Settings.from_environment()

    get_settings.cache_clear()


def test_settings_require_both_ip_protection_keys(
    monkeypatch: MonkeyPatch,
) -> None:
    """Hash and encryption keys should always be configured together."""

    monkeypatch.setenv(
        "NORGOTH_IP_HASH_KEY",
        base64.b64encode(b"h" * 32).decode("ascii"),
    )
    monkeypatch.delenv("NORGOTH_IP_ENCRYPTION_KEY", raising=False)
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    with pytest.raises(
        ValueError,
        match="must be configured together",
    ):
        Settings.from_environment()

    get_settings.cache_clear()


def test_settings_reject_short_ip_hash_key(
    monkeypatch: MonkeyPatch,
) -> None:
    """The IP hash key should decode to at least 32 bytes."""

    monkeypatch.setenv(
        "NORGOTH_IP_HASH_KEY",
        base64.b64encode(b"h" * 31).decode("ascii"),
    )
    monkeypatch.setenv(
        "NORGOTH_IP_ENCRYPTION_KEY",
        base64.b64encode(b"e" * 32).decode("ascii"),
    )
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    with pytest.raises(
        ValueError,
        match="at least 32 bytes",
    ):
        Settings.from_environment()

    get_settings.cache_clear()


def test_settings_reject_invalid_ip_encryption_key_length(
    monkeypatch: MonkeyPatch,
) -> None:
    """The AES encryption key should decode to exactly 32 bytes."""

    monkeypatch.setenv(
        "NORGOTH_IP_HASH_KEY",
        base64.b64encode(b"h" * 32).decode("ascii"),
    )
    monkeypatch.setenv(
        "NORGOTH_IP_ENCRYPTION_KEY",
        base64.b64encode(b"e" * 31).decode("ascii"),
    )
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    with pytest.raises(
        ValueError,
        match="exactly 32 bytes",
    ):
        Settings.from_environment()

    get_settings.cache_clear()


def test_discord_oauth_settings_are_optional_together(
    monkeypatch: MonkeyPatch,
) -> None:
    """The API should start before Discord OAuth is configured."""

    _clear_ip_environment(monkeypatch)
    _clear_discord_environment(monkeypatch)
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.discord_client_id is None
    assert settings.discord_client_secret is None
    assert settings.discord_redirect_uri is None

    get_settings.cache_clear()


def test_settings_read_discord_oauth_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    """Discord OAuth settings should be read together."""

    _clear_ip_environment(monkeypatch)
    monkeypatch.setenv(
        "NORGOTH_DISCORD_CLIENT_ID",
        "123456789012345678",
    )
    monkeypatch.setenv(
        "NORGOTH_DISCORD_CLIENT_SECRET",
        "discord-client-secret",
    )
    monkeypatch.setenv(
        "NORGOTH_DISCORD_REDIRECT_URI",
        "http://localhost:8000/api/v1/oauth/discord/callback",
    )
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.discord_client_id == "123456789012345678"
    assert settings.discord_client_secret == "discord-client-secret"
    assert settings.discord_redirect_uri == ("http://localhost:8000/api/v1/oauth/discord/callback")

    get_settings.cache_clear()


@pytest.mark.parametrize(
    "missing_environment_name",
    [
        "NORGOTH_DISCORD_CLIENT_ID",
        "NORGOTH_DISCORD_CLIENT_SECRET",
        "NORGOTH_DISCORD_REDIRECT_URI",
    ],
)
def test_settings_require_all_discord_oauth_values(
    monkeypatch: MonkeyPatch,
    missing_environment_name: str,
) -> None:
    """Partial Discord OAuth configuration should be rejected."""

    _clear_ip_environment(monkeypatch)
    monkeypatch.setenv(
        "NORGOTH_DISCORD_CLIENT_ID",
        "123456789012345678",
    )
    monkeypatch.setenv(
        "NORGOTH_DISCORD_CLIENT_SECRET",
        "discord-client-secret",
    )
    monkeypatch.setenv(
        "NORGOTH_DISCORD_REDIRECT_URI",
        "http://localhost:8000/api/v1/oauth/discord/callback",
    )
    monkeypatch.delenv(
        missing_environment_name,
        raising=False,
    )
    get_settings.cache_clear()

    with pytest.raises(
        ValueError,
        match="must be configured together",
    ):
        Settings.from_environment()

    get_settings.cache_clear()
