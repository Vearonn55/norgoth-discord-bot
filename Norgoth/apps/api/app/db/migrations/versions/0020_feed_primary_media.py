"""Add feed_messages.primary_media_url for embed media.

Revision ID: 0020_feed_primary_media
Revises: 0019_feed_channels
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_feed_primary_media"
down_revision: str | Sequence[str] | None = "0019_feed_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feed_messages",
        sa.Column("primary_media_url", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feed_messages", "primary_media_url")
