"""Discord snowflake parsing and account-age calculations."""

from __future__ import annotations

from datetime import UTC, datetime

_DISCORD_EPOCH_MILLISECONDS = 1_420_070_400_000
_DISCORD_TIMESTAMP_SHIFT = 22


class InvalidDiscordSnowflakeError(ValueError):
    """Raised when a Discord snowflake cannot be parsed."""


def parse_discord_snowflake(value: str) -> int:
    """Validate and return a Discord snowflake as an integer."""

    normalized_value = value.strip()

    if (
        not normalized_value
        or not normalized_value.isdigit()
        or not 1 <= len(normalized_value) <= 20
    ):
        message = "Discord snowflake must contain 1 to 20 digits."
        raise InvalidDiscordSnowflakeError(message)

    snowflake = int(normalized_value)

    if snowflake <= 0:
        message = "Discord snowflake must be greater than zero."
        raise InvalidDiscordSnowflakeError(message)

    return snowflake


def get_discord_snowflake_created_at(value: str) -> datetime:
    """Return the UTC creation time encoded in a Discord snowflake."""

    snowflake = parse_discord_snowflake(value)

    timestamp_milliseconds = (snowflake >> _DISCORD_TIMESTAMP_SHIFT) + _DISCORD_EPOCH_MILLISECONDS

    try:
        return datetime.fromtimestamp(
            timestamp_milliseconds / 1_000,
            tz=UTC,
        )
    except (OSError, OverflowError, ValueError) as error:
        message = "Discord snowflake contains an invalid timestamp."
        raise InvalidDiscordSnowflakeError(message) from error


def get_discord_account_age_days(
    value: str,
    *,
    current_time: datetime | None = None,
) -> int:
    """Return the completed age of a Discord account in UTC days."""

    created_at = get_discord_snowflake_created_at(value)
    resolved_current_time = current_time or datetime.now(UTC)

    if resolved_current_time.tzinfo is None:
        message = "Current time must include timezone information."
        raise ValueError(message)

    normalized_current_time = resolved_current_time.astimezone(UTC)

    if created_at > normalized_current_time:
        message = "Discord account creation time is in the future."
        raise InvalidDiscordSnowflakeError(message)

    account_age = normalized_current_time - created_at

    return account_age.days


__all__ = [
    "InvalidDiscordSnowflakeError",
    "get_discord_account_age_days",
    "get_discord_snowflake_created_at",
    "parse_discord_snowflake",
]
