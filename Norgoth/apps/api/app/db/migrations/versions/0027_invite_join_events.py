"""Invite join attribution events for durable recent-join history.

Revision ID: 0027_invite_join_events
Revises: 0026_cn_avatar_indexes
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_invite_join_events"
down_revision = "0026_cn_avatar_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_join_events",
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
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("member_id", sa.String(length=32), nullable=False),
        sa.Column("inviter_id", sa.String(length=32), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("attribution", sa.String(length=32), nullable=False),
        sa.Column("rejoin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite_join_events")),
    )
    op.create_index(
        "ix_invite_join_events_guild_joined",
        "invite_join_events",
        ["guild_id", "joined_at"],
    )
    op.create_index(
        "ix_invite_join_events_guild_member",
        "invite_join_events",
        ["guild_id", "member_id"],
    )
    op.create_unique_constraint(
        "uq_invite_join_events_guild_member_joined",
        "invite_join_events",
        ["guild_id", "member_id", "joined_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_invite_join_events_guild_member_joined",
        "invite_join_events",
        type_="unique",
    )
    op.drop_index("ix_invite_join_events_guild_member", table_name="invite_join_events")
    op.drop_index("ix_invite_join_events_guild_joined", table_name="invite_join_events")
    op.drop_table("invite_join_events")
