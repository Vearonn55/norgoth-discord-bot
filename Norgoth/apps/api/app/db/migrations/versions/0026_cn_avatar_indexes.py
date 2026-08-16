"""Widen CN avatar URLs, add freshness column and list/analytics indexes.

Revision ID: 0026_cn_avatar_indexes
Revises: 0025_verification_panel_message
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_cn_avatar_indexes"
down_revision = "0025_verification_panel_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "content_creator_sources",
        "avatar_url",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
    op.add_column(
        "content_creator_sources",
        sa.Column("avatar_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_guild_content_subscriptions_guild_created",
        "guild_content_subscriptions",
        ["guild_id", "created_at"],
    )
    op.create_index(
        "ix_notification_jobs_created_at",
        "notification_jobs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_jobs_created_at", table_name="notification_jobs")
    op.drop_index(
        "ix_guild_content_subscriptions_guild_created",
        table_name="guild_content_subscriptions",
    )
    op.drop_column("content_creator_sources", "avatar_checked_at")
    op.alter_column(
        "content_creator_sources",
        "avatar_url",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
