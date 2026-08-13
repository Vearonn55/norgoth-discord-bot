"""Per-guild verification settings (scalars only; IDs live in bindings)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enum_column import str_enum
from app.models.enums import RiskAction
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.guild import Guild


class GuildSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store scalar verification settings for one guild."""

    __tablename__ = "guild_settings"
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
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
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

    # Note: ``deny_vpn_or_proxy`` / ``deny_shared_ip`` are the detector ENABLED
    # flags. The resulting action (deny vs. manual review) is carried by the
    # ``*_action`` columns below.
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

    vpn_or_proxy_action: Mapped[RiskAction] = mapped_column(
        str_enum(RiskAction, "vpn_or_proxy_action", length=16),
        nullable=False,
        default=RiskAction.DENY,
        server_default=RiskAction.DENY.value,
    )

    shared_ip_action: Mapped[RiskAction] = mapped_column(
        str_enum(RiskAction, "shared_ip_action", length=16),
        nullable=False,
        default=RiskAction.DENY,
        server_default=RiskAction.DENY.value,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Discord message ID of the published verification panel (nullable until
    # first successful publish). Used to edit-or-recreate on Save.
    panel_message_id: Mapped[str | None] = mapped_column(
        DiscordSnowflake(),
        nullable=True,
    )

    guild: Mapped[Guild] = relationship("Guild", back_populates="settings")
