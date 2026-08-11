"""Add ticket_panels_configs for durable ticket panel snapshots.

Revision ID: 0015_ticket_panels_configs
Revises: 0014_invite_logging_configs
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_ticket_panels_configs"
down_revision: str | Sequence[str] | None = "0014_invite_logging_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_panels_configs",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_object()"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_panels_configs")),
        sa.UniqueConstraint(
            "guild_id", name=op.f("uq_ticket_panels_configs_guild_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("ticket_panels_configs")
