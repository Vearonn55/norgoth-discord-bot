"""Add panel_message_id to guild_settings for verification panel idempotency.

Revision ID: 0025_verification_panel_message
Revises: 0024_rss_feeds
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_verification_panel_message"
down_revision = "0024_rss_feeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("panel_message_id", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "panel_message_id")
