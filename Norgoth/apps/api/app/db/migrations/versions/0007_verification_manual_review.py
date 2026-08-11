"""High-risk guilds + manual-review verification state.

Adds the ``guild_high_risk_guilds`` table, widens the
``verification_attempts.status`` and ``guild_role_bindings.purpose`` CHECK
constraints to include ``manual_review``, and adds the
``high_risk_guild_detected`` / ``reviewed_by`` / ``reviewed_at`` columns used by
the manual-review workflow.

Revision ID: 0007_verification_manual_review
Revises: 0abbfb2f339a
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models.types

revision: str = "0007_verification_manual_review"
down_revision: str | Sequence[str] | None = "0abbfb2f339a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""

    op.create_table(
        "guild_high_risk_guilds",
        sa.Column("guild_id", sa.Uuid(), nullable=False),
        sa.Column(
            "high_risk_discord_guild_id",
            app.models.types.DiscordSnowflake(length=20),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_by",
            app.models.types.DiscordSnowflake(length=20),
            nullable=True,
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
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name=op.f("fk_guild_high_risk_guilds_guild_id_guilds"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guild_high_risk_guilds")),
        sa.UniqueConstraint(
            "guild_id",
            "high_risk_discord_guild_id",
            name="uq_guild_high_risk_guilds_owner_target",
        ),
    )

    op.add_column(
        "verification_attempts",
        sa.Column(
            "high_risk_guild_detected",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "verification_attempts",
        sa.Column(
            "reviewed_by",
            app.models.types.DiscordSnowflake(length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "verification_attempts",
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Widen the non-native enum CHECK constraints to allow manual_review.
    op.execute(
        "ALTER TABLE verification_attempts "
        "DROP CONSTRAINT IF EXISTS ck_verification_attempts_verification_status"
    )
    op.execute(
        "ALTER TABLE verification_attempts "
        "ADD CONSTRAINT ck_verification_attempts_verification_status "
        "CHECK (status IN ('success', 'failed', 'manual_review'))"
    )

    op.execute(
        "ALTER TABLE guild_role_bindings "
        "DROP CONSTRAINT IF EXISTS ck_guild_role_bindings_guild_role_purpose"
    )
    op.execute(
        "ALTER TABLE guild_role_bindings "
        "ADD CONSTRAINT ck_guild_role_bindings_guild_role_purpose "
        "CHECK (purpose IN ('verified', 'unverified', 'member', 'manual_review'))"
    )


def downgrade() -> None:
    """Revert this migration."""

    op.execute(
        "ALTER TABLE guild_role_bindings "
        "DROP CONSTRAINT IF EXISTS ck_guild_role_bindings_guild_role_purpose"
    )
    op.execute(
        "ALTER TABLE guild_role_bindings "
        "ADD CONSTRAINT ck_guild_role_bindings_guild_role_purpose "
        "CHECK (purpose IN ('verified', 'unverified', 'member'))"
    )

    op.execute(
        "ALTER TABLE verification_attempts "
        "DROP CONSTRAINT IF EXISTS ck_verification_attempts_verification_status"
    )
    op.execute(
        "ALTER TABLE verification_attempts "
        "ADD CONSTRAINT ck_verification_attempts_verification_status "
        "CHECK (status IN ('success', 'failed'))"
    )

    op.drop_column("verification_attempts", "reviewed_at")
    op.drop_column("verification_attempts", "reviewed_by")
    op.drop_column("verification_attempts", "high_risk_guild_detected")

    op.drop_table("guild_high_risk_guilds")
