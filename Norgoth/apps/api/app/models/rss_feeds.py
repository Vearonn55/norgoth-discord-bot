"""ORM models for guild RSS / Atom feed subscriptions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class RssFeedConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-guild RSS/Atom feed subscription."""

    __tablename__ = "rss_feed_configs"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "feed_url_hash",
            name="uq_rss_feed_configs_guild_url",
        ),
        Index("ix_rss_feed_configs_guild_id", "guild_id"),
        Index(
            "ix_rss_feed_configs_enabled_next_poll",
            "enabled",
            "next_poll_at",
        ),
    )

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False)
    feed_url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    mention_role_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="300"
    )
    format_hint: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_modified: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_poll_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    items: Mapped[list["RssFeedItem"]] = relationship(
        "RssFeedItem",
        back_populates="feed",
        cascade="all, delete-orphan",
    )


class RssFeedItem(UUIDPrimaryKeyMixin, Base):
    """Seen / published item keys for a feed (dedupe + bootstrap)."""

    __tablename__ = "rss_feed_items"
    __table_args__ = (
        UniqueConstraint("feed_id", "item_key", name="uq_rss_feed_items_feed_key"),
        Index("ix_rss_feed_items_feed_id", "feed_id"),
    )

    feed_id: Mapped[UUID] = mapped_column(
        ForeignKey("rss_feed_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_key: Mapped[str] = mapped_column(String(512), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    posted_message_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    skipped_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    feed: Mapped[RssFeedConfig] = relationship("RssFeedConfig", back_populates="items")
