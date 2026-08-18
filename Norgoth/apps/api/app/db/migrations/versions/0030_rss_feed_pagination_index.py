"""Add RSS guild-created-id index for paginated listing.

Revision ID: 0030_rss_feed_pagination_index
Revises: 0029_embed_delivery_idempotency
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "0030_rss_feed_pagination_index"
down_revision = "0029_embed_delivery_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_rss_feed_configs_guild_created_id",
        "rss_feed_configs",
        ["guild_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rss_feed_configs_guild_created_id", table_name="rss_feed_configs")
