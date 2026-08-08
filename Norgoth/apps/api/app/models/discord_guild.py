"""Discord guild persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.blacklisted_guild import BlacklistedGuild
    from app.models.configuration import Configuration
    from app.models.user_list_entry import UserListEntry
    from app.models.verification_log import VerificationLog


class DiscordGuild(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represent one Discord server using Norgoth Verification."""

    __tablename__ = "discord_guilds"
    __table_args__ = (
        CheckConstraint(
            "char_length(discord_guild_name) BETWEEN 1 AND 100",
            name="discord_guild_name_length",
        ),
    )

    discord_guild_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
        unique=True,
    )

    discord_guild_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    discord_owner_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    configuration: Mapped[Configuration | None] = relationship(
        "Configuration",
        back_populates="guild",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )

    verification_logs: Mapped[list[VerificationLog]] = relationship(
        "VerificationLog",
        back_populates="guild",
        cascade="all, delete-orphan",
    )

    user_list_entries: Mapped[list[UserListEntry]] = relationship(
        "UserListEntry",
        back_populates="guild",
        cascade="all, delete-orphan",
    )

    blacklisted_guilds: Mapped[list[BlacklistedGuild]] = relationship(
        "BlacklistedGuild",
        back_populates="guild",
        cascade="all, delete-orphan",
    )
