"""Persist Discord message ids for late actor enrichment edits.

Revision ID: 0032_server_event_log_discord_message
Revises: 0031_invite_lifecycle
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032_server_event_log_discord_message"
down_revision = "0031_invite_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "server_event_log_entries",
        sa.Column("discord_channel_id", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "server_event_log_entries",
        sa.Column("discord_message_id", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("server_event_log_entries", "discord_message_id")
    op.drop_column("server_event_log_entries", "discord_channel_id")
