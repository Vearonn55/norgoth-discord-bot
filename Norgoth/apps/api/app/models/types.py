"""Reusable SQLAlchemy types for Discord identifiers."""

import re

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

_DISCORD_SNOWFLAKE_PATTERN = re.compile(r"^[0-9]{1,20}$")


class DiscordSnowflake(TypeDecorator[str]):
    """Store a Discord snowflake as a validated decimal string."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> str | None:
        """Validate a value before sending it to the database."""

        if value is None:
            return None

        if _DISCORD_SNOWFLAKE_PATTERN.fullmatch(value) is None:
            message = "Discord snowflakes must contain between 1 and 20 ASCII decimal digits."
            raise ValueError(message)

        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> str | None:
        """Return stored Discord snowflakes as strings."""

        return value
