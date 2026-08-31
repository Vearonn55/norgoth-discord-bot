"""Active Discord guild bans for verification ban-evasion correlation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.guild import Guild


class GuildActiveBan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Track whether a Discord user is actively banned from a managed guild."""

    __tablename__ = "guild_active_bans"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "discord_user_id",
            name="uq_guild_active_bans_guild_user",
        ),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discord_user_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    banned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    unbanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    username_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name_snapshot: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="gateway_ban",
        server_default="gateway_ban",
    )

    guild: Mapped[Guild] = relationship("Guild")
