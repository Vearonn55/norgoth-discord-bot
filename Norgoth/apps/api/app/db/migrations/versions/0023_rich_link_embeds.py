"""Rich Link Embeds feature config table.

Revision ID: 0023_rich_link_embeds
Revises: 0022_media_provider
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_rich_link_embeds"
down_revision = "0022_media_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rich_link_embeds_configs",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rich_link_embeds_configs")),
        sa.UniqueConstraint(
            "guild_id", name=op.f("uq_rich_link_embeds_configs_guild_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("rich_link_embeds_configs")
