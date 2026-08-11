"""Discord guild persistence model (source of truth)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.discord_user import DiscordUser
    from app.models.guild_bindings import (
        GuildChannelBinding,
        GuildRoleBinding,
    )
    from app.models.guild_high_risk_guild import GuildHighRiskGuild
    from app.models.guild_moderation_entry import GuildModerationEntry
    from app.models.guild_settings import GuildSettings
    from app.models.verification_attempt import VerificationAttempt


class Guild(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represent one Discord server managed by Norgoth."""

    __tablename__ = "guilds"
    __table_args__ = (
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 100",
            name="guild_name_length",
        ),
    )

    discord_guild_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("discord_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    owner: Mapped[DiscordUser | None] = relationship("DiscordUser")

    settings: Mapped[GuildSettings | None] = relationship(
        "GuildSettings",
        back_populates="guild",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )

    role_bindings: Mapped[list[GuildRoleBinding]] = relationship(
        "GuildRoleBinding",
        back_populates="guild",
        cascade="all, delete-orphan",
    )

    channel_bindings: Mapped[list[GuildChannelBinding]] = relationship(
        "GuildChannelBinding",
        back_populates="guild",
        cascade="all, delete-orphan",
    )

    verification_attempts: Mapped[list[VerificationAttempt]] = relationship(
        "VerificationAttempt",
        back_populates="guild",
        cascade="all, delete-orphan",
    )

    moderation_entries: Mapped[list[GuildModerationEntry]] = relationship(
        "GuildModerationEntry",
        back_populates="guild",
        cascade="all, delete-orphan",
    )

    high_risk_guilds: Mapped[list[GuildHighRiskGuild]] = relationship(
        "GuildHighRiskGuild",
        back_populates="guild",
        cascade="all, delete-orphan",
    )
