"""Add storage_provider to embed_media_assets for S3-ready uploads.

Revision ID: 0022_media_provider
Revises: 0021_feed_author_snapshot
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_media_provider"
down_revision = "0021_feed_author_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "embed_media_assets",
        sa.Column(
            "storage_provider",
            sa.String(length=32),
            nullable=False,
            server_default="local",
        ),
    )
    op.add_column(
        "embed_media_assets",
        sa.Column("storage_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("embed_media_assets", "storage_key")
    op.drop_column("embed_media_assets", "storage_provider")
