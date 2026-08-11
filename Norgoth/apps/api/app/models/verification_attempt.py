"""Verification attempt persistence model (source of truth)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import UUIDPrimaryKeyMixin
from app.models.enum_column import str_enum
from app.models.enums import VerificationStatus
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.discord_user import DiscordUser
    from app.models.guild import Guild


class VerificationAttempt(UUIDPrimaryKeyMixin, Base):
    """Store one successful or failed Discord verification attempt."""

    __tablename__ = "verification_attempts"

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("discord_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[VerificationStatus] = mapped_column(
        str_enum(VerificationStatus, "verification_status", length=16),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    ip_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    ip_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    vpn_or_proxy_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    shared_ip_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    high_risk_guild_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # IDs of the configured High Risk Servers the user belonged to at the time
    # of the attempt. Stored as a JSON array of Discord snowflakes (strings) so
    # reviewers see an explicit, auditable reason for the manual review.
    matched_high_risk_guild_ids: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        DiscordSnowflake(),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    guild: Mapped[Guild] = relationship("Guild", back_populates="verification_attempts")
    user: Mapped[DiscordUser] = relationship("DiscordUser")
