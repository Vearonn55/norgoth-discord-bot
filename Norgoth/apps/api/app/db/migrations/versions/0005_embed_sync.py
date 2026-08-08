"""Add embed message revision tracking for publish/re-sync drift detection.

Revision ID: 0005_embed_sync
Revises: 0004_logging_config
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_embed_sync"
down_revision: str | None = "0004_logging_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "embed_messages",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "embed_message_deliveries",
        sa.Column("deployed_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("embed_message_deliveries", "deployed_version")
    op.drop_column("embed_messages", "version")
