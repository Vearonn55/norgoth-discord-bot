"""Add feed_messages author display snapshot columns.

Revision ID: 0021_feed_author_snapshot
Revises: 0020_feed_primary_media
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_feed_author_snapshot"
down_revision = "0020_feed_primary_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feed_messages",
        sa.Column("author_display_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "feed_messages",
        sa.Column("author_avatar_url", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feed_messages", "author_avatar_url")
    op.drop_column("feed_messages", "author_display_name")
