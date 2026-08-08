"""Discord verification configuration persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.discord_guild import DiscordGuild


class Configuration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store verification settings for one Discord guild."""

    __tablename__ = "configurations"
    __table_args__ = (
        CheckConstraint(
            "minimum_account_age_days BETWEEN 0 AND 3650",
            name="minimum_account_age_days_range",
        ),
        CheckConstraint(
            "session_timeout_seconds BETWEEN 60 AND 3600",
            name="session_timeout_seconds_range",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "discord_guilds.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    verification_channel_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    log_channel_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    verified_role_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    unverified_role_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    member_role_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    minimum_account_age_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    session_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=900,
        server_default="900",
    )

    deny_vpn_or_proxy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    deny_shared_ip: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    guild: Mapped[DiscordGuild] = relationship(
        "DiscordGuild",
        back_populates="configuration",
    )
