"""Create content notification tables.

Revision ID: 0002_content_notifications
Revises: 0001_initial
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_content_notifications"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_creator_sources",
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("platform_creator_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("profile_url", sa.String(length=500), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("canonical_url", sa.String(length=500), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_object()"),
            nullable=False,
        ),
        sa.Column(
            "monitor_status",
            sa.String(length=64),
            server_default="active",
            nullable=False,
        ),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_creator_sources"),
        sa.UniqueConstraint(
            "platform",
            "platform_creator_id",
            name="uq_content_creator_sources_platform_creator",
        ),
    )
    op.create_index(
        "ix_content_creator_sources_platform",
        "content_creator_sources",
        ["platform"],
    )

    op.create_table(
        "notification_templates",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform_default_for", sa.String(length=32), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embed_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_templates"),
    )
    op.create_index(
        "ix_notification_templates_guild_id",
        "notification_templates",
        ["guild_id"],
    )

    op.create_table(
        "notification_sender_styles",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_sender_styles"),
    )
    op.create_index(
        "ix_notification_sender_styles_guild_id",
        "notification_sender_styles",
        ["guild_id"],
    )

    op.create_table(
        "platform_subscriptions",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column("external_subscription_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("callback_secret_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=64),
            server_default="active",
            nullable=False,
        ),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["content_creator_sources.id"],
            name="fk_platform_subs_source_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_subscriptions"),
        sa.UniqueConstraint(
            "source_id",
            "transport",
            name="uq_platform_subscriptions_source_transport",
        ),
    )
    op.create_index(
        "ix_platform_subscriptions_source_id",
        "platform_subscriptions",
        ["source_id"],
    )

    op.create_table(
        "platform_monitor_cursors",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cursor", sa.String(length=500), nullable=True),
        sa.Column("last_seen_content_id", sa.String(length=200), nullable=True),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["content_creator_sources.id"],
            name="fk_platform_cursors_source_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_monitor_cursors"),
        sa.UniqueConstraint("source_id", name="uq_platform_monitor_cursors_source_id"),
    )
    op.create_index(
        "ix_platform_monitor_cursors_next_check_at",
        "platform_monitor_cursors",
        ["next_check_at"],
    )

    op.create_table(
        "normalized_content_events",
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.String(length=200), nullable=False),
        sa.Column("creator_name", sa.String(length=200), nullable=False),
        sa.Column("creator_avatar", sa.String(length=500), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content_url", sa.String(length=1000), nullable=True),
        sa.Column("playable_url", sa.String(length=1000), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_live", sa.Boolean(), nullable=True),
        sa.Column("game", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("viewer_count", sa.Integer(), nullable=True),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_object()"),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["content_creator_sources.id"],
            name="fk_norm_events_source_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_normalized_content_events"),
        sa.UniqueConstraint(
            "platform",
            "external_content_id",
            "event_type",
            name="uq_normalized_content_events_dedupe",
        ),
    )
    op.create_index(
        "ix_normalized_content_events_source_id",
        "normalized_content_events",
        ["source_id"],
    )
    op.create_index(
        "ix_normalized_content_events_received_at",
        "normalized_content_events",
        ["received_at"],
    )

    op.create_table(
        "discord_managed_webhooks",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
        sa.Column("webhook_id", sa.String(length=32), nullable=False),
        sa.Column("encrypted_webhook_token", sa.LargeBinary(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=64),
            server_default="healthy",
            nullable=False,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_discord_managed_webhooks"),
        sa.UniqueConstraint(
            "guild_id",
            "channel_id",
            name="uq_discord_managed_webhooks_guild_channel",
        ),
    )

    op.create_table(
        "guild_content_subscriptions",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("destination_channel_id", sa.String(length=32), nullable=False),
        sa.Column("ping_role_id", sa.String(length=32), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("sender_style_id", sa.Uuid(), nullable=True),
        sa.Column(
            "event_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_array()"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "status",
            sa.String(length=64),
            server_default="waiting_first_event",
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.Column("last_event_id", sa.Uuid(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["content_creator_sources.id"],
            name="fk_guild_subs_source_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["notification_templates.id"],
            name="fk_guild_subs_template_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sender_style_id"],
            ["notification_sender_styles.id"],
            name="fk_guild_subs_sender_style_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guild_content_subscriptions"),
        sa.UniqueConstraint(
            "guild_id",
            "source_id",
            name="uq_guild_content_subscriptions_guild_source",
        ),
    )
    op.create_index(
        "ix_guild_content_subscriptions_source_id",
        "guild_content_subscriptions",
        ["source_id"],
    )
    op.create_index(
        "ix_guild_content_subscriptions_guild_enabled",
        "guild_content_subscriptions",
        ["guild_id", "enabled"],
    )

    op.create_table(
        "notification_jobs",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["normalized_content_events.id"],
            name="fk_notif_jobs_event_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["guild_content_subscriptions.id"],
            name="fk_notif_jobs_subscription_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_jobs"),
        sa.UniqueConstraint(
            "event_id",
            "subscription_id",
            name="uq_notification_jobs_event_subscription",
        ),
    )
    op.create_index(
        "ix_notification_jobs_event_id",
        "notification_jobs",
        ["event_id"],
    )
    op.create_index(
        "ix_notification_jobs_subscription_id",
        "notification_jobs",
        ["subscription_id"],
    )
    op.create_index(
        "ix_notification_jobs_status_next_attempt",
        "notification_jobs",
        ["status", "next_attempt_at"],
    )

    op.create_table(
        "notification_delivery_attempts",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["notification_jobs.id"],
            name="fk_notif_attempts_job_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_delivery_attempts"),
    )
    op.create_index(
        "ix_notification_delivery_attempts_job_id",
        "notification_delivery_attempts",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_table("notification_delivery_attempts")
    op.drop_table("notification_jobs")
    op.drop_table("guild_content_subscriptions")
    op.drop_table("discord_managed_webhooks")
    op.drop_table("normalized_content_events")
    op.drop_table("platform_monitor_cursors")
    op.drop_table("platform_subscriptions")
    op.drop_table("notification_sender_styles")
    op.drop_table("notification_templates")
    op.drop_table("content_creator_sources")
