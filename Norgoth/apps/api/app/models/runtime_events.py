"""Durable runtime event/state tables (Postgres source of truth).

These record discrete runtime events and durable per-guild state that the bot
produces. The bot stays DB-free and POSTs discrete events to internal API ingest
endpoints; hot per-message counters (XP, analytics, invites) stay Redis-first and
are rolled up here. High-volume tables keep raw Discord snowflake strings (no
``discord_users`` FK) so ingest never requires a user-dimension upsert.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import DiscordSnowflake


class RaidIncident(UUIDPrimaryKeyMixin, Base):
    """A detected raid, with its join sample and lifecycle status."""

    __tablename__ = "raid_incidents"
    __table_args__ = (
        Index("ix_raid_incidents_guild_detected", "guild_id", "detected_at"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    joins_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    join_sample: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_array()
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    actions: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_array()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class HoneypotTrigger(UUIDPrimaryKeyMixin, Base):
    """A member that posted in a honeypot trap channel."""

    __tablename__ = "honeypot_triggers"
    __table_args__ = (
        Index("ix_honeypot_triggers_guild_created", "guild_id", "created_at"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    user_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    punishment: Mapped[str] = mapped_column(String(32), nullable=False, default="log_only")
    details: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModerationLogEntry(UUIDPrimaryKeyMixin, Base):
    """An append-only moderation action record."""

    __tablename__ = "moderation_log_entries"
    __table_args__ = (
        Index("ix_moderation_log_entries_guild_created", "guild_id", "created_at"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    moderator_id: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ServerEventLogEntry(UUIDPrimaryKeyMixin, Base):
    """An append-only generic server event record (mirror of the Redis list)."""

    __tablename__ = "server_event_log_entries"
    __table_args__ = (
        Index("ix_server_event_log_entries_guild_created", "guild_id", "created_at"),
        UniqueConstraint(
            "guild_id",
            "source_event_id",
            name="uq_server_event_log_guild_source",
        ),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    has_detail: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    payload: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_object()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InviteJoinEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable per-join invite attribution for a guild."""

    __tablename__ = "invite_join_events"
    __table_args__ = (
        Index("ix_invite_join_events_guild_joined", "guild_id", "joined_at"),
        Index("ix_invite_join_events_guild_member", "guild_id", "member_id"),
        UniqueConstraint(
            "guild_id",
            "member_id",
            "joined_at",
            name="uq_invite_join_events_guild_member_joined",
        ),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    member_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    inviter_id: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attribution: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    rejoin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InviteCounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-inviter join/leave/rejoin counters for a guild."""

    __tablename__ = "invite_counters"
    __table_args__ = (
        UniqueConstraint("guild_id", "inviter_id", name="uq_invite_counters_guild_inviter"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    inviter_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    joins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leaves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejoins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MemberXp(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Rolled-up per-member XP for a guild (Redis ZSETs are the hot cache)."""

    __tablename__ = "member_xp"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_member_xp_guild_user"),
        Index("ix_member_xp_guild_xp", "guild_id", "xp"),
        Index("ix_member_xp_guild_text_xp", "guild_id", "text_xp"),
        Index("ix_member_xp_guild_voice_xp", "guild_id", "voice_xp"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    user_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    text_xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    voice_xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class AnalyticsDaily(UUIDPrimaryKeyMixin, Base):
    """Daily analytics rollup per guild (Redis keeps intraday unique sets)."""

    __tablename__ = "analytics_daily"
    __table_args__ = (
        UniqueConstraint("guild_id", "day", name="uq_analytics_daily_guild_day"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_authors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    joins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leaves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_uniques: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A support ticket. ``number`` is a per-guild sequence (replaces ``:counter``)."""

    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("guild_id", "number", name="uq_tickets_guild_number"),
        Index("ix_tickets_guild_status", "guild_id", "status"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_id: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    opener_id: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    transcript: Mapped[TicketTranscript | None] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        uselist=False,
    )
    share_tokens: Mapped[list[TicketShareToken]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )


class TicketTranscript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The full text transcript of a closed ticket (1:1 with a ticket)."""

    __tablename__ = "ticket_transcripts"

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    ticket: Mapped[Ticket] = relationship(back_populates="transcript")


class TicketShareToken(TimestampMixin, Base):
    """A bearer token granting time-boxed public access to a transcript."""

    __tablename__ = "ticket_share_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    ticket: Mapped[Ticket] = relationship(back_populates="share_tokens")


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A broadcast/DM campaign. Schedule/queue via status + timestamps."""

    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaigns_guild_status", "guild_id", "status"),
        Index("ix_campaigns_status_launch", "status", "launch_at"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    platform_messages: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_object()
    )
    audience: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_object()
    )
    raw_payload: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_object()
    )
    created_by: Mapped[str | None] = mapped_column(DiscordSnowflake(), nullable=True)
    launch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    recipient_results: Mapped[list[CampaignRecipientResult]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    activity: Mapped[list[CampaignActivity]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignRecipientResult(UUIDPrimaryKeyMixin, Base):
    """Per-recipient delivery outcome for a campaign."""

    __tablename__ = "campaign_recipient_results"
    __table_args__ = (
        Index("ix_campaign_recipient_results_campaign", "campaign_id"),
    )

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    campaign: Mapped[Campaign] = relationship(back_populates="recipient_results")


class CampaignActivity(UUIDPrimaryKeyMixin, Base):
    """An activity/audit entry in a campaign's lifecycle."""

    __tablename__ = "campaign_activity"
    __table_args__ = (Index("ix_campaign_activity_campaign", "campaign_id"),)

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=func.jsonb_build_object()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    campaign: Mapped[Campaign] = relationship(back_populates="activity")


class CampaignUnsubscribe(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user who opted out of campaign DMs for a guild."""

    __tablename__ = "campaign_unsubscribes"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_campaign_unsubscribes_guild_user"),
    )

    guild_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
    user_id: Mapped[str] = mapped_column(DiscordSnowflake(), nullable=False)
