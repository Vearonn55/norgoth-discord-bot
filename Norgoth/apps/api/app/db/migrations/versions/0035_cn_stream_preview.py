"""Add stream preview columns for content notification live events.

Revision ID: 0035_cn_stream_preview
Revises: 0034_manual_review_queue_idx
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_cn_stream_preview"
down_revision = "0034_manual_review_queue_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "normalized_content_events",
        sa.Column("stream_preview_url", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "normalized_content_events",
        sa.Column("stream_preview_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "normalized_content_events",
        sa.Column("preview_capture_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "normalized_content_events",
        sa.Column("preview_captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "normalized_content_events",
        sa.Column("stream_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "guild_content_subscriptions",
        sa.Column(
            "notification_locale",
            sa.String(length=5),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_content_subscriptions", "notification_locale")
    op.drop_column("normalized_content_events", "stream_started_at")
    op.drop_column("normalized_content_events", "preview_captured_at")
    op.drop_column("normalized_content_events", "preview_capture_status")
    op.drop_column("normalized_content_events", "stream_preview_storage_key")
    op.drop_column("normalized_content_events", "stream_preview_url")
