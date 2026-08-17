"""Add queryable identity columns to server_event_log_entries.

Revision ID: 0028_server_event_log_detail
Revises: 0027_invite_join_events
Create Date: 2026-08-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_server_event_log_detail"
down_revision = "0027_invite_join_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "server_event_log_entries",
        sa.Column("category", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "server_event_log_entries",
        sa.Column("action", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "server_event_log_entries",
        sa.Column("actor_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "server_event_log_entries",
        sa.Column("actor_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "server_event_log_entries",
        sa.Column("source_event_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "server_event_log_entries",
        sa.Column(
            "has_detail",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_unique_constraint(
        "uq_server_event_log_guild_source",
        "server_event_log_entries",
        ["guild_id", "source_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_server_event_log_guild_source",
        "server_event_log_entries",
        type_="unique",
    )
    op.drop_column("server_event_log_entries", "has_detail")
    op.drop_column("server_event_log_entries", "source_event_id")
    op.drop_column("server_event_log_entries", "actor_name")
    op.drop_column("server_event_log_entries", "actor_id")
    op.drop_column("server_event_log_entries", "action")
    op.drop_column("server_event_log_entries", "category")
