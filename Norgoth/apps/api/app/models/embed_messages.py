"""SQLAlchemy models for reusable embed messages and uploaded media assets."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EmbedMediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A guild-scoped uploaded image served from local storage."""

    __tablename__ = "embed_media_assets"
    __table_args__ = (Index("ix_embed_media_assets_guild_id", "guild_id"),)

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    public_url: Mapped[str] = mapped_column(String(600), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="local"
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class EmbedMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A reusable, guild-scoped saved Discord embed message."""

    __tablename__ = "embed_messages"
    __table_args__ = (Index("ix_embed_messages_guild_id", "guild_id"),)

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Desired revision. Bumped whenever publishable content (content/embed)
    # changes so deliveries can be flagged "edited — needs re-sync".
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)

    deliveries: Mapped[list["EmbedMessageDelivery"]] = relationship(
        back_populates="embed_message",
        cascade="all, delete-orphan",
    )


class EmbedMessageDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks a sent Discord message so a saved embed can be re-synced."""

    __tablename__ = "embed_message_deliveries"
    __table_args__ = (
        Index("ix_embed_message_deliveries_guild_id", "guild_id"),
        Index("ix_embed_message_deliveries_message", "embed_message_id"),
        Index(
            "uq_embed_delivery_idempotency",
            "embed_message_id",
            "channel_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    embed_message_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "embed_messages.id",
            ondelete="CASCADE",
            name="fk_embed_delivery_message_id",
        ),
        nullable=False,
    )
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    discord_message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discord_message_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="bot"
    )
    # Which Norgoth feature owns this deployment. Generic Re-Sync may recreate a
    # missing message only for library-owned deployments; feature-owned ones
    # (e.g. Self-Assignable Roles) require components and are flagged for feature
    # repair instead. Runtime SAR detection (role-menu binding) is authoritative
    # even when this column still reads the default.
    # embed_library | self_assignable_role
    owner_feature: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="embed_library"
    )
    # synced | message_missing | channel_missing | permission_missing |
    # webhook_missing | needs_feature_repair | pending | error
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The embed version this delivery last reflected in Discord. When it lags
    # behind EmbedMessage.version the copy is stale and needs a re-sync.
    deployed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    embed_message: Mapped["EmbedMessage"] = relationship(back_populates="deliveries")
