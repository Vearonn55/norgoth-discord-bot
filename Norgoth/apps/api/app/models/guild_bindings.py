"""Normalized role and channel bindings for a guild."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enum_column import str_enum
from app.models.enums import GuildChannelPurpose, GuildRolePurpose
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.guild import Guild


class GuildRoleBinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Bind a purpose (verified/unverified/member) to a Discord role."""

    __tablename__ = "guild_role_bindings"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "purpose",
            name="uq_guild_role_bindings_guild_purpose",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
    )

    purpose: Mapped[GuildRolePurpose] = mapped_column(
        str_enum(GuildRolePurpose, "guild_role_purpose"),
        nullable=False,
    )

    role_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    guild: Mapped[Guild] = relationship("Guild", back_populates="role_bindings")


class GuildChannelBinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Bind a purpose (verification/log) to a Discord channel."""

    __tablename__ = "guild_channel_bindings"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "purpose",
            name="uq_guild_channel_bindings_guild_purpose",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
    )

    purpose: Mapped[GuildChannelPurpose] = mapped_column(
        str_enum(GuildChannelPurpose, "guild_channel_purpose"),
        nullable=False,
    )

    channel_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    guild: Mapped[Guild] = relationship("Guild", back_populates="channel_bindings")
