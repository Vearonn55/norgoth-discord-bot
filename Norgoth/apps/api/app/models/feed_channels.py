"""Feed Channels durable models (tracked messages, votes, slots, author stats)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake


class FeedMessage(UUIDPrimaryKeyMixin, Base):
    """A tracked source message eligible for Feed ranking."""

    __tablename__ = "feed_messages"
    __table_args__ = (
        UniqueConstraint(
            "guild_id", "message_id", name="uq_feed_messages_guild_message"
        ),
        Index(
            "ix_feed_messages_guild_rank",
            "guild_id",
            "status",
            "net_score",
            "upvote_count",
            "created_at",
            "message_id",
        ),
        Index("ix_feed_messages_guild_created", "guild_id", "created_at"),
        Index("ix_feed_messages_guild_author", "guild_id", "author_id"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    channel_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    message_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    author_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    author_display_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    author_avatar_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content_excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_media_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upvote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downvote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    row_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FeedVote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical per-user vote on an original tracked message."""

    __tablename__ = "feed_votes"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "message_id",
            "voter_id",
            name="uq_feed_votes_guild_message_voter",
        ),
        Index("ix_feed_votes_guild_message", "guild_id", "message_id"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    message_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    voter_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    vote: Mapped[str] = mapped_column(String(8), nullable=False)  # up | down


class FeedEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable Discord feed-channel slot for a ranking window."""

    __tablename__ = "feed_entries"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "window",
            "rank",
            name="uq_feed_entries_guild_window_rank",
        ),
        UniqueConstraint(
            "guild_id",
            "feed_message_id",
            name="uq_feed_entries_guild_feed_message",
        ),
        Index("ix_feed_entries_guild_window", "guild_id", "window"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    window: Mapped[str] = mapped_column(String(16), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    feed_channel_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    feed_message_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(
        DiscordSnowflake(), nullable=True
    )


class FeedAuthorStats(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-author aggregate Net Upvotes for Top Net Upvote leaderboards."""

    __tablename__ = "feed_author_stats"
    __table_args__ = (
        UniqueConstraint(
            "guild_id", "user_id", name="uq_feed_author_stats_guild_user"
        ),
        Index("ix_feed_author_stats_guild_net", "guild_id", "net_score"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    user_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    net_score: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    upvote_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    downvote_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
