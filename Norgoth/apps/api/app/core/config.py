"""Application configuration loaded from environment variables."""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from functools import lru_cache


def _read_boolean(name: str, *, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized_value = value.strip().lower()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    message = f"Environment variable {name!r} must be one of: 1, true, yes, on, 0, false, no, off."
    raise ValueError(message)


def _read_int(name: str, *, default: int) -> int:
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return int(value.strip())
    except ValueError as error:
        message = f"Environment variable {name!r} must be an integer."
        raise ValueError(message) from error


def _read_optional_string(name: str) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    normalized_value = value.strip()

    if not normalized_value:
        return None

    return normalized_value


def _read_optional_base64_bytes(name: str) -> bytes | None:
    value = _read_optional_string(name)

    if value is None:
        return None

    try:
        decoded_value = base64.b64decode(
            value,
            validate=True,
        )
    except (binascii.Error, ValueError) as error:
        message = f"Environment variable {name!r} must contain valid Base64."
        raise ValueError(message) from error

    return decoded_value


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings."""

    app_name: str
    app_version: str
    environment: str
    api_v1_prefix: str
    log_level: str
    enable_docs: bool
    database_url: str | None
    database_echo: bool
    ip_hash_key: bytes | None = None
    ip_encryption_key: bytes | None = None
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    discord_redirect_uri: str | None = None
    discord_dashboard_redirect_uri: str | None = None
    dashboard_public_url: str | None = None
    discord_application_id: str | None = None
    discord_bot_token: str | None = None
    proxycheck_api_key: str | None = None
    auth_enforced: bool = False
    webhook_encryption_key: bytes | None = None
    youtube_api_key: str | None = None
    twitch_client_id: str | None = None
    twitch_client_secret: str | None = None
    twitch_eventsub_secret: str | None = None
    kick_client_id: str | None = None
    kick_client_secret: str | None = None
    x_api_bearer_token: str | None = None
    public_api_url: str | None = None
    upload_dir: str = "var/uploads"
    max_upload_bytes: int = 8 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> Settings:
        """Build application settings from process environment variables."""

        environment = (
            os.getenv(
                "NORGOTH_ENVIRONMENT",
                "development",
            )
            .strip()
            .lower()
        )

        log_level = (
            os.getenv(
                "NORGOTH_LOG_LEVEL",
                "INFO",
            )
            .strip()
            .upper()
        )

        allowed_environments = {
            "development",
            "testing",
            "staging",
            "production",
        }

        if environment not in allowed_environments:
            allowed_values = ", ".join(sorted(allowed_environments))
            message = (
                "NORGOTH_ENVIRONMENT contains an unsupported value. "
                f"Expected one of: {allowed_values}."
            )
            raise ValueError(message)

        allowed_log_levels = {
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
        }

        if log_level not in allowed_log_levels:
            allowed_values = ", ".join(sorted(allowed_log_levels))
            message = (
                "NORGOTH_LOG_LEVEL contains an unsupported value. "
                f"Expected one of: {allowed_values}."
            )
            raise ValueError(message)

        ip_hash_key = _read_optional_base64_bytes("NORGOTH_IP_HASH_KEY")
        ip_encryption_key = _read_optional_base64_bytes("NORGOTH_IP_ENCRYPTION_KEY")

        if (ip_hash_key is None) != (ip_encryption_key is None):
            message = (
                "NORGOTH_IP_HASH_KEY and NORGOTH_IP_ENCRYPTION_KEY must be configured together."
            )
            raise ValueError(message)

        if ip_hash_key is not None and len(ip_hash_key) < 32:
            message = "NORGOTH_IP_HASH_KEY must decode to at least 32 bytes."
            raise ValueError(message)

        if ip_encryption_key is not None and len(ip_encryption_key) != 32:
            message = "NORGOTH_IP_ENCRYPTION_KEY must decode to exactly 32 bytes."
            raise ValueError(message)

        webhook_encryption_key = _read_optional_base64_bytes(
            "NORGOTH_WEBHOOK_ENCRYPTION_KEY"
        )
        if webhook_encryption_key is not None and len(webhook_encryption_key) != 32:
            message = (
                "NORGOTH_WEBHOOK_ENCRYPTION_KEY must decode to exactly 32 bytes."
            )
            raise ValueError(message)

        discord_client_id = _read_optional_string("NORGOTH_DISCORD_CLIENT_ID")
        discord_client_secret = _read_optional_string("NORGOTH_DISCORD_CLIENT_SECRET")
        discord_redirect_uri = _read_optional_string("NORGOTH_DISCORD_REDIRECT_URI")

        discord_values = (
            discord_client_id,
            discord_client_secret,
            discord_redirect_uri,
        )
        configured_discord_values = sum(value is not None for value in discord_values)

        if configured_discord_values not in {0, 3}:
            message = (
                "NORGOTH_DISCORD_CLIENT_ID, "
                "NORGOTH_DISCORD_CLIENT_SECRET, and "
                "NORGOTH_DISCORD_REDIRECT_URI must be configured together."
            )
            raise ValueError(message)

        dashboard_redirect = _read_optional_string(
            "NORGOTH_DISCORD_DASHBOARD_REDIRECT_URI"
        )
        if dashboard_redirect is None and discord_redirect_uri is not None:
            # Default: sibling path under the same API host.
            dashboard_redirect = discord_redirect_uri.replace(
                "/oauth/discord/callback",
                "/oauth/discord/dashboard/callback",
            )

        return cls(
            app_name="Norgoth Verification API",
            app_version="0.1.0",
            environment=environment,
            api_v1_prefix="/api/v1",
            log_level=log_level,
            enable_docs=_read_boolean(
                "NORGOTH_ENABLE_DOCS",
                default=environment != "production",
            ),
            database_url=_read_optional_string(
                "NORGOTH_DATABASE_URL",
            ),
            database_echo=_read_boolean(
                "NORGOTH_DATABASE_ECHO",
                default=False,
            ),
            ip_hash_key=ip_hash_key,
            ip_encryption_key=ip_encryption_key,
            discord_client_id=discord_client_id,
            discord_client_secret=discord_client_secret,
            discord_redirect_uri=discord_redirect_uri,
            discord_dashboard_redirect_uri=dashboard_redirect,
            dashboard_public_url=_read_optional_string("NORGOTH_DASHBOARD_URL")
            or _read_optional_string("NEXT_PUBLIC_DASHBOARD_URL")
            or "http://127.0.0.1:3000",
            discord_application_id=_read_optional_string("DISCORD_APPLICATION_ID")
            or discord_client_id,
            discord_bot_token=_read_optional_string("DISCORD_BOT_TOKEN"),
            proxycheck_api_key=_read_optional_string("NORGOTH_PROXYCHECK_API_KEY"),
            auth_enforced=_read_boolean(
                "NORGOTH_AUTH_ENFORCED",
                default=environment == "production",
            ),
            webhook_encryption_key=webhook_encryption_key,
            youtube_api_key=_read_optional_string("YOUTUBE_API_KEY"),
            twitch_client_id=_read_optional_string("TWITCH_CLIENT_ID"),
            twitch_client_secret=_read_optional_string("TWITCH_CLIENT_SECRET"),
            twitch_eventsub_secret=_read_optional_string("TWITCH_EVENTSUB_SECRET"),
            kick_client_id=_read_optional_string("KICK_CLIENT_ID"),
            kick_client_secret=_read_optional_string("KICK_CLIENT_SECRET"),
            x_api_bearer_token=_read_optional_string("X_API_BEARER_TOKEN")
            or _read_optional_string("TWITTER_BEARER_TOKEN"),
            public_api_url=_read_optional_string("NORGOTH_PUBLIC_API_URL")
            or _read_optional_string("NORGOTH_API_URL"),
            upload_dir=_read_optional_string("NORGOTH_UPLOAD_DIR") or "var/uploads",
            max_upload_bytes=_read_int(
                "NORGOTH_MAX_UPLOAD_BYTES",
                default=8 * 1024 * 1024,
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings.from_environment()
