"""Add enabled flag on logging_channels for per-category gating.

Revision ID: 0016_logging_channel_enabled
Revises: 0015_ticket_panels_configs
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_logging_channel_enabled"
down_revision: str | Sequence[str] | None = "0015_ticket_panels_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "logging_channels",
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("logging_channels", "enabled")
