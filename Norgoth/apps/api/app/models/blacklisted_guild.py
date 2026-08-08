"""Blacklisted Discord guild persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.discord_guild import DiscordGuild


class BlacklistedGuild(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store a Discord guild blocked by one configured server."""

    __tablename__ = "blacklisted_guilds"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "blacklisted_discord_guild_id",
            name="uq_blacklisted_guilds_owner_target",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "discord_guilds.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    blacklisted_discord_guild_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    guild: Mapped[DiscordGuild] = relationship(
        "DiscordGuild",
        back_populates="blacklisted_guilds",
    )
