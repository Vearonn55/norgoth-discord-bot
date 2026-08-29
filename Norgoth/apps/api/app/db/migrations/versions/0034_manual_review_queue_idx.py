"""Add indexes for open manual-review queue lookups.

Revision ID: 0034_manual_review_queue_idx
Revises: 0033_link_embeds_providers
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034_manual_review_queue_idx"
down_revision = "0033_link_embeds_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ux_verification_attempts_open_manual_review",
        "verification_attempts",
        ["guild_id", "user_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'manual_review' AND reviewed_at IS NULL"
        ),
    )
    op.create_index(
        "ix_verification_attempts_guild_status_created",
        "verification_attempts",
        ["guild_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verification_attempts_guild_status_created",
        table_name="verification_attempts",
    )
    op.drop_index(
        "ux_verification_attempts_open_manual_review",
        table_name="verification_attempts",
    )
