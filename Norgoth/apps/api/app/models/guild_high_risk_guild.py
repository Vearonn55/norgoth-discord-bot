"""Guilds whose members are routed to manual verification review."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.guild import Guild


class GuildHighRiskGuild(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store a Discord guild flagged high-risk by one configured server.

    A verifying user who is a member of any high-risk guild is routed to
    ``manual_review`` instead of being auto-verified (unless a stronger deny
    rule applies, or the user is whitelisted). The Discord guild snowflake is
    the authoritative identifier; guild names are mutable and non-unique.
    """

    __tablename__ = "guild_high_risk_guilds"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "high_risk_discord_guild_id",
            name="uq_guild_high_risk_guilds_owner_target",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
    )

    high_risk_discord_guild_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    created_by: Mapped[str | None] = mapped_column(
        DiscordSnowflake(),
        nullable=True,
    )

    guild: Mapped[Guild] = relationship(
        "Guild", back_populates="high_risk_guilds"
    )
