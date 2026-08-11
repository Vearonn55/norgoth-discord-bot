"""SQLAlchemy models for multi-platform content notifications."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ContentCreatorSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_creator_sources"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "platform_creator_id",
            name="uq_content_creator_sources_platform_creator",
        ),
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    platform_creator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    profile_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=func.jsonb_build_object(),
    )
    monitor_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="active",
        server_default="active",
    )
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    platform_subscriptions: Mapped[list[PlatformSubscription]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    guild_subscriptions: Mapped[list[GuildContentSubscription]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class PlatformSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "transport",
            name="uq_platform_subscriptions_source_transport",
        ),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_creator_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    external_subscription_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    callback_secret_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="active",
        server_default="active",
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source: Mapped[ContentCreatorSource] = relationship(
        back_populates="platform_subscriptions",
    )


class PlatformMonitorCursor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_monitor_cursors"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_creator_sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    next_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_cursor: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_seen_content_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )


class NormalizedContentEventRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "normalized_content_events"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_content_id",
            "event_type",
            name="uq_normalized_content_events_dedupe",
        ),
        Index("ix_normalized_content_events_received_at", "received_at"),
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_creator_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_content_id: Mapped[str] = mapped_column(String(200), nullable=False)
    creator_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    creator_avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    playable_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_live: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    game: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    viewer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=func.jsonb_build_object(),
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class NotificationTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_guild_id", "guild_id"),
    )

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform_default_for: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class NotificationSenderStyle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_sender_styles"
    __table_args__ = (
        Index("ix_notification_sender_styles_guild_id", "guild_id"),
    )

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class GuildContentSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "guild_content_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "source_id",
            name="uq_guild_content_subscriptions_guild_source",
        ),
        Index("ix_guild_content_subscriptions_guild_enabled", "guild_id", "enabled"),
    )

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_creator_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_channel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    ping_role_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_style_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notification_sender_styles.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_types: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=func.jsonb_build_array(),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="waiting_first_event",
        server_default="waiting_first_event",
    )
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_event_id: Mapped[UUID | None] = mapped_column(nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source: Mapped[ContentCreatorSource] = relationship(
        back_populates="guild_subscriptions",
    )
    template: Mapped[NotificationTemplate | None] = relationship()
    sender_style: Mapped[NotificationSenderStyle | None] = relationship()


class DiscordManagedWebhook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discord_managed_webhooks"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "channel_id",
            name="uq_discord_managed_webhooks_guild_channel",
        ),
    )

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    webhook_id: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_webhook_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="healthy",
        server_default="healthy",
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class NotificationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "subscription_id",
            name="uq_notification_jobs_event_subscription",
        ),
        Index("ix_notification_jobs_status_next_attempt", "status", "next_attempt_at"),
    )

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("normalized_content_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("guild_content_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    attempts: Mapped[list[NotificationDeliveryAttempt]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class NotificationDeliveryAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        Index("ix_notification_delivery_attempts_job_id", "job_id"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    job: Mapped[NotificationJob] = relationship(back_populates="attempts")
