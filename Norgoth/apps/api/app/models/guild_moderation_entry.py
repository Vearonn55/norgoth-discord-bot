"""Manual whitelist/blacklist entries for a guild's members."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enum_column import str_enum
from app.models.enums import UserListType

if TYPE_CHECKING:
    from app.models.discord_user import DiscordUser
    from app.models.guild import Guild


class GuildModerationEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store a manually whitelisted or blacklisted Discord user."""

    __tablename__ = "guild_moderation_entries"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "user_id",
            name="uq_guild_moderation_entries_guild_user",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("discord_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    list_type: Mapped[UserListType] = mapped_column(
        str_enum(UserListType, "user_list_type", length=16),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    guild: Mapped[Guild] = relationship("Guild", back_populates="moderation_entries")
    user: Mapped[DiscordUser] = relationship("DiscordUser")
