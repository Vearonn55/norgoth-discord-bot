"""SQLAlchemy models for the config-driven logging system.

A guild has at most one :class:`LoggingConfiguration`. Each configuration owns
one or more :class:`LoggingChannel` rows (the "log groups", each mapped to a
Discord channel) and a set of :class:`LoggingEventMapping` rows that route a
specific Discord event type to a channel with an embed colour.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DiscordLoggingEventType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Seeded lookup of loggable Discord event types (from the catalog).

    ``key`` matches the ``event_type`` string used across the API snapshot and
    the bot's read contract; ``group_key`` mirrors the wizard grouping.
    """

    __tablename__ = "discord_logging_event_types"

    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    group_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    default_color: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LoggingConfiguration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Top-level, per-guild logging configuration."""

    __tablename__ = "logging_configurations"
    __table_args__ = (
        Index(
            "ux_logging_configurations_guild_id",
            "guild_id",
            unique=True,
        ),
    )

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # draft = created by wizard but not yet provisioned/active; active = live.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft"
    )
    # Discord category the log channels live under (optional).
    category_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # True when Norgoth created the category (so it may manage/delete it).
    norgoth_managed_category: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)

    channels: Mapped[list["LoggingChannel"]] = relationship(
        back_populates="configuration",
        cascade="all, delete-orphan",
    )
    event_mappings: Mapped[list["LoggingEventMapping"]] = relationship(
        back_populates="configuration",
        cascade="all, delete-orphan",
    )


class LoggingChannel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A logging group mapped to a Discord channel."""

    __tablename__ = "logging_channels"
    __table_args__ = (
        Index("ix_logging_channels_config", "logging_configuration_id"),
        Index("ix_logging_channels_guild_id", "guild_id"),
        UniqueConstraint(
            "logging_configuration_id",
            "key",
            name="uq_logging_channels_config_key",
        ),
    )

    logging_configuration_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "logging_configurations.id",
            ondelete="CASCADE",
            name="fk_logging_channel_config_id",
        ),
        nullable=False,
    )
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    # Stable group key (e.g. "member", "message", "moderation", or custom slug).
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # True when Norgoth created the channel (so it may manage/delete it).
    norgoth_managed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Default embed colour (Discord decimal). Event overrides take precedence.
    default_color: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Category-level gate: when false, events for this channel are omitted from
    # the Redis routing snapshot without deleting mappings or channel rows.
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    configuration: Mapped["LoggingConfiguration"] = relationship(
        back_populates="channels"
    )
    event_mappings: Mapped[list["LoggingEventMapping"]] = relationship(
        back_populates="channel",
    )


class LoggingEventMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Routes a specific event type to a channel with an embed colour."""

    __tablename__ = "logging_event_mappings"
    __table_args__ = (
        Index("ix_logging_event_mappings_config", "logging_configuration_id"),
        Index("ix_logging_event_mappings_guild_id", "guild_id"),
        UniqueConstraint(
            "logging_configuration_id",
            "event_type",
            name="uq_logging_event_mappings_config_event",
        ),
    )

    logging_configuration_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "logging_configurations.id",
            ondelete="CASCADE",
            name="fk_logging_event_config_id",
        ),
        nullable=False,
    )
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Soft reference to the seeded lookup. The `event_type` string stays
    # authoritative for the bot snapshot; this FK links to the catalog row when
    # the type is known/seeded (best-effort, nullable to tolerate new types).
    event_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "discord_logging_event_types.id",
            ondelete="SET NULL",
            name="fk_logging_event_type_id",
        ),
        nullable=True,
    )
    logging_channel_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "logging_channels.id",
            ondelete="SET NULL",
            name="fk_logging_event_channel_id",
        ),
        nullable=True,
    )
    # Per-event embed colour override (Discord decimal). Falls back to the
    # channel's default_color when null.
    color: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    configuration: Mapped["LoggingConfiguration"] = relationship(
        back_populates="event_mappings"
    )
    channel: Mapped["LoggingChannel"] = relationship(
        back_populates="event_mappings"
    )
