"""System-wide audit trail for durable configuration and state changes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import DiscordSnowflake


class SystemAuditLog(Base):
    """Append-only record of who changed what, when."""

    __tablename__ = "system_audit_log"
    __table_args__ = (
        Index("ix_system_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_system_audit_log_guild_created", "guild_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    guild_id: Mapped[str | None] = mapped_column(
        DiscordSnowflake(),
        nullable=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("discord_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    changes: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
