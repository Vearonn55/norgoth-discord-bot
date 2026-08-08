"""Discord user whitelist and blacklist persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserListType
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.discord_guild import DiscordGuild


class UserListEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store a manually whitelisted or blacklisted Discord user."""

    __tablename__ = "user_list_entries"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "discord_user_id",
            name="uq_user_list_entries_guild_user",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "discord_guilds.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    discord_user_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )

    list_type: Mapped[UserListType] = mapped_column(
        Enum(
            UserListType,
            name="user_list_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_type: [member.value for member in enum_type],
            length=16,
        ),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    guild: Mapped[DiscordGuild] = relationship(
        "DiscordGuild",
        back_populates="user_list_entries",
    )
