"""Tests for Discord snowflake parsing and account-age calculations."""

from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.discord.snowflake import (
    InvalidDiscordSnowflakeError,
    get_discord_account_age_days,
    get_discord_snowflake_created_at,
    parse_discord_snowflake,
)

DISCORD_EPOCH = datetime(2015, 1, 1, tzinfo=UTC)


def _create_snowflake(created_at: datetime) -> str:
    """Create a deterministic Discord snowflake for a UTC timestamp."""

    timestamp_milliseconds = int((created_at - DISCORD_EPOCH).total_seconds() * 1_000)
    snowflake = timestamp_milliseconds << 22

    return str(snowflake)


def test_parses_valid_discord_snowflake() -> None:
    """A numeric Discord snowflake should be returned as an integer."""

    snowflake = "175928847299117063"

    result = parse_discord_snowflake(snowflake)

    assert result == 175_928_847_299_117_063


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "not-a-snowflake",
        "-1",
        "0",
        "123456789012345678901",
    ],
)
def test_rejects_invalid_discord_snowflake(value: str) -> None:
    """Malformed Discord snowflakes should be rejected."""

    with pytest.raises(InvalidDiscordSnowflakeError):
        parse_discord_snowflake(value)


def test_returns_discord_account_creation_time() -> None:
    """Snowflake timestamps should decode into UTC datetimes."""

    created_at = datetime(
        2020,
        5,
        17,
        12,
        30,
        45,
        tzinfo=UTC,
    )
    snowflake = _create_snowflake(created_at)

    result = get_discord_snowflake_created_at(snowflake)

    assert result == created_at


def test_returns_completed_account_age_days() -> None:
    """Account age should contain only completed UTC days."""

    created_at = datetime(
        2024,
        1,
        1,
        12,
        0,
        tzinfo=UTC,
    )
    current_time = created_at + timedelta(
        days=30,
        hours=23,
        minutes=59,
    )
    snowflake = _create_snowflake(created_at)

    result = get_discord_account_age_days(
        snowflake,
        current_time=current_time,
    )

    assert result == 30


def test_returns_zero_for_new_account() -> None:
    """An account less than one day old should have age zero."""

    created_at = datetime(
        2025,
        1,
        1,
        12,
        0,
        tzinfo=UTC,
    )
    current_time = created_at + timedelta(hours=23)
    snowflake = _create_snowflake(created_at)

    result = get_discord_account_age_days(
        snowflake,
        current_time=current_time,
    )

    assert result == 0


def test_normalizes_current_time_to_utc() -> None:
    """Timezone-aware current times should be normalized to UTC."""

    created_at = datetime(
        2024,
        1,
        1,
        0,
        0,
        tzinfo=UTC,
    )
    current_time = datetime.fromisoformat("2024-01-31T03:00:00+03:00")
    snowflake = _create_snowflake(created_at)

    result = get_discord_account_age_days(
        snowflake,
        current_time=current_time,
    )

    assert result == 30


def test_rejects_naive_current_time() -> None:
    """Current time must always contain timezone information."""

    snowflake = _create_snowflake(
        datetime(
            2024,
            1,
            1,
            tzinfo=UTC,
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        get_discord_account_age_days(
            snowflake,
            current_time=datetime(2024, 2, 1),
        )


def test_rejects_future_account_creation_time() -> None:
    """A snowflake created after the current time should be rejected."""

    current_time = datetime(
        2025,
        1,
        1,
        tzinfo=UTC,
    )
    snowflake = _create_snowflake(current_time + timedelta(days=1))

    with pytest.raises(
        InvalidDiscordSnowflakeError,
        match="future",
    ):
        get_discord_account_age_days(
            snowflake,
            current_time=current_time,
        )


def test_known_discord_epoch_snowflake() -> None:
    """The first timestamp after the Discord epoch should decode correctly."""

    snowflake = str(1 << 22)

    result = get_discord_snowflake_created_at(snowflake)

    assert result == datetime(
        2015,
        1,
        1,
        0,
        0,
        0,
        1_000,
        tzinfo=UTC,
    )
