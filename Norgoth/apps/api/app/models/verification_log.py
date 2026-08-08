"""Verification attempt log persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import UUIDPrimaryKeyMixin
from app.models.enums import VerificationStatus
from app.models.types import DiscordSnowflake

if TYPE_CHECKING:
    from app.models.discord_guild import DiscordGuild


class VerificationLog(UUIDPrimaryKeyMixin, Base):
    """Store one successful or failed Discord verification attempt."""

    __tablename__ = "verification_logs"

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "discord_guilds.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    discord_user_id: Mapped[str] = mapped_column(
        DiscordSnowflake(),
        nullable=False,
        index=True,
    )

    status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            name="verification_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_type: [member.value for member in enum_type],
            length=16,
        ),
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

    blacklisted_guild_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    guild: Mapped[DiscordGuild] = relationship(
        "DiscordGuild",
        back_populates="verification_logs",
    )
