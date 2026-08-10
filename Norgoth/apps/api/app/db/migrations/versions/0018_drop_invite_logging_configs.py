"""Drop invite_logging_configs (Invite Log Messaging removed).

Revision ID: 0018_drop_invite_logging_configs
Revises: 0017_member_xp_text_voice
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_drop_invite_logging_configs"
down_revision: str | Sequence[str] | None = "0017_member_xp_text_voice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("invite_logging_configs")


def downgrade() -> None:
    op.create_table(
        "invite_logging_configs",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
