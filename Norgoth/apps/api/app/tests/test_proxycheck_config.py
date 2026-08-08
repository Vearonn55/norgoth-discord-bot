"""Tests for proxycheck.io application configuration."""

from pytest import MonkeyPatch

from app.core.config import Settings, get_settings


def test_proxycheck_api_key_is_optional(
    monkeypatch: MonkeyPatch,
) -> None:
    """The API should support proxycheck.io keyless mode."""

    monkeypatch.delenv(
        "NORGOTH_PROXYCHECK_API_KEY",
        raising=False,
    )
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.proxycheck_api_key is None

    get_settings.cache_clear()


def test_settings_read_proxycheck_api_key(
    monkeypatch: MonkeyPatch,
) -> None:
    """A configured proxycheck.io key should be loaded."""

    monkeypatch.setenv(
        "NORGOTH_PROXYCHECK_API_KEY",
        "proxycheck-api-key",
    )
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.proxycheck_api_key == "proxycheck-api-key"

    get_settings.cache_clear()


def test_blank_proxycheck_api_key_is_treated_as_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    """Whitespace-only keys should enable keyless mode."""

    monkeypatch.setenv(
        "NORGOTH_PROXYCHECK_API_KEY",
        "   ",
    )
    get_settings.cache_clear()

    settings = Settings.from_environment()

    assert settings.proxycheck_api_key is None

    get_settings.cache_clear()
