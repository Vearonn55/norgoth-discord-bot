"""Split member_xp into text_xp and voice_xp with backfill.

Revision ID: 0017_member_xp_text_voice
Revises: 0016_logging_channel_enabled
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_member_xp_text_voice"
down_revision: str | Sequence[str] | None = "0016_logging_channel_enabled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "member_xp",
        sa.Column(
            "text_xp",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "member_xp",
        sa.Column(
            "voice_xp",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    # Historical totals cannot be unmixed — attribute prior XP to text.
    op.execute(sa.text("UPDATE member_xp SET text_xp = xp, voice_xp = 0"))
    op.create_index(
        "ix_member_xp_guild_text_xp",
        "member_xp",
        ["guild_id", "text_xp"],
        unique=False,
    )
    op.create_index(
        "ix_member_xp_guild_voice_xp",
        "member_xp",
        ["guild_id", "voice_xp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_member_xp_guild_voice_xp", table_name="member_xp")
    op.drop_index("ix_member_xp_guild_text_xp", table_name="member_xp")
    op.drop_column("member_xp", "voice_xp")
    op.drop_column("member_xp", "text_xp")
