"""Add guild_active_bans for verification ban-evasion correlation.

Revision ID: 0036_guild_active_bans
Revises: 0035_cn_stream_preview
Create Date: 2026-08-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036_guild_active_bans"
down_revision = "0035_cn_stream_preview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_active_bans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.Uuid(), nullable=False),
        sa.Column("discord_user_id", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unbanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("username_snapshot", sa.String(length=200), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="gateway_ban"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guild_id",
            "discord_user_id",
            name="uq_guild_active_bans_guild_user",
        ),
    )
    op.create_index(
        "ix_guild_active_bans_guild_active",
        "guild_active_bans",
        ["guild_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_guild_active_bans_guild_active", table_name="guild_active_bans")
    op.drop_table("guild_active_bans")
