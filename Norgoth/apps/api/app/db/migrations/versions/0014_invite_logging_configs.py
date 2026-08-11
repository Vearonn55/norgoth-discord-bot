"""Add invite_logging_configs for TinyMCE invite join/leave log templates.

Revision ID: 0014_invite_logging_configs
Revises: 0013_drop_embed_publish_targets
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_invite_logging_configs"
down_revision: str | Sequence[str] | None = "0013_drop_embed_publish_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invite_logging_configs",
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
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite_logging_configs")),
        sa.UniqueConstraint(
            "guild_id", name=op.f("uq_invite_logging_configs_guild_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("invite_logging_configs")
