"""Track embed deploy idempotency keys and all Discord message ids.

Revision ID: 0029_embed_delivery_idempotency
Revises: 0028_server_event_log_detail
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029_embed_delivery_idempotency"
down_revision = "0028_server_event_log_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "embed_message_deliveries",
        sa.Column(
            "discord_message_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "embed_message_deliveries",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_embed_delivery_idempotency",
        "embed_message_deliveries",
        ["embed_message_id", "channel_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_embed_delivery_idempotency",
        table_name="embed_message_deliveries",
    )
    op.drop_column("embed_message_deliveries", "idempotency_key")
    op.drop_column("embed_message_deliveries", "discord_message_ids")
