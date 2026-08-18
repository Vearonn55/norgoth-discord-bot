"""Invite lifecycle snapshots for one-use / deleted invite attribution.

Revision ID: 0031_invite_lifecycle
Revises: 0030_rss_feed_pagination_index
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_invite_lifecycle"
down_revision = "0030_rss_feed_pagination_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_lifecycle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("guild_id", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("inviter_id", sa.String(length=20), nullable=True),
        sa.Column("inviter_name_snapshot", sa.String(length=128), nullable=True),
        sa.Column("channel_id", sa.String(length=20), nullable=True),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("max_age", sa.Integer(), nullable=True),
        sa.Column(
            "temporary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at_discord", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("disappeared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "invite_kind",
            sa.String(length=16),
            nullable=False,
            server_default="standard",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite_lifecycle")),
        sa.UniqueConstraint(
            "guild_id",
            "code",
            name="uq_invite_lifecycle_guild_code",
        ),
    )
    op.create_index(
        "ix_invite_lifecycle_guild_status_disappeared",
        "invite_lifecycle",
        ["guild_id", "status", "disappeared_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invite_lifecycle_guild_status_disappeared",
        table_name="invite_lifecycle",
    )
    op.drop_table("invite_lifecycle")
