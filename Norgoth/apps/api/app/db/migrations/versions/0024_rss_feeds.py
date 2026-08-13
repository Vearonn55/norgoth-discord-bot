"""Alembic migration for RSS feed configs and seen items.

Revision ID: 0024_rss_feeds
Revises: 0023_rich_link_embeds
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_rss_feeds"
down_revision = "0023_rich_link_embeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rss_feed_configs",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("feed_url_hash", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
        sa.Column("mention_role_id", sa.String(length=32), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "poll_interval_seconds",
            sa.Integer(),
            server_default="300",
            nullable=False,
        ),
        sa.Column("format_hint", sa.String(length=16), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "failure_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rss_feed_configs")),
        sa.UniqueConstraint(
            "guild_id",
            "feed_url_hash",
            name="uq_rss_feed_configs_guild_url",
        ),
    )
    op.create_index(
        "ix_rss_feed_configs_guild_id",
        "rss_feed_configs",
        ["guild_id"],
        unique=False,
    )
    op.create_index(
        "ix_rss_feed_configs_enabled_next_poll",
        "rss_feed_configs",
        ["enabled", "next_poll_at"],
        unique=False,
    )

    op.create_table(
        "rss_feed_items",
        sa.Column("feed_id", sa.UUID(), nullable=False),
        sa.Column("item_key", sa.String(length=512), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("posted_message_id", sa.String(length=32), nullable=True),
        sa.Column("skipped_reason", sa.String(length=32), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["rss_feed_configs.id"],
            name=op.f("fk_rss_feed_items_feed_id_rss_feed_configs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rss_feed_items")),
        sa.UniqueConstraint(
            "feed_id",
            "item_key",
            name="uq_rss_feed_items_feed_key",
        ),
    )
    op.create_index(
        "ix_rss_feed_items_feed_id",
        "rss_feed_items",
        ["feed_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rss_feed_items_feed_id", table_name="rss_feed_items")
    op.drop_table("rss_feed_items")
    op.drop_index(
        "ix_rss_feed_configs_enabled_next_poll", table_name="rss_feed_configs"
    )
    op.drop_index("ix_rss_feed_configs_guild_id", table_name="rss_feed_configs")
    op.drop_table("rss_feed_configs")
