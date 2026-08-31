"""Add manual-review evidence columns to verification_attempts.

Revision ID: 0037_verification_review_evidence
Revises: 0036_guild_active_bans
Create Date: 2026-08-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0037_verification_review_evidence"
down_revision = "0036_guild_active_bans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "verification_attempts",
        sa.Column(
            "banned_ip_match_detected",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "verification_attempts",
        sa.Column(
            "matched_banned_user_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "verification_attempts",
        sa.Column(
            "review_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("verification_attempts", "review_evidence")
    op.drop_column("verification_attempts", "matched_banned_user_ids")
    op.drop_column("verification_attempts", "banned_ip_match_detected")
