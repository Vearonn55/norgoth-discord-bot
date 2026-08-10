"""Central Discord user dimension.

Any Discord user referenced by the system (guild owners, moderation actors,
subscription creators, audit actors) resolves to one row here so those
references can be proper foreign keys instead of loose snowflake strings.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake


class DiscordUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Discord user referenced anywhere in the system."""

    __tablename__ = "discord_users"

    discord_user_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
        unique=True,
    )

    username_cache: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
