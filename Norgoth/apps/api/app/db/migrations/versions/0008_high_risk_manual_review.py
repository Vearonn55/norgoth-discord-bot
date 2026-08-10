"""Retire Blacklisted Guilds; capture matched high-risk servers.

Transforms the legacy hard-rejection "Blacklisted Guild" system into the
manual-review "High Risk Server" system:

* Adds ``verification_attempts.matched_high_risk_guild_ids`` (JSON array of the
  configured High Risk Server IDs a user belonged to at attempt time).
* Migrates existing ``guild_blacklisted_guilds`` rows into
  ``guild_high_risk_guilds`` (``created_by`` becomes NULL; ``ON CONFLICT DO
  NOTHING`` so pre-existing high-risk entries win), changing their semantics
  from automatic rejection to manual-review triggering.
* Drops the ``guild_blacklisted_guilds`` table and the now-unused
  ``verification_attempts.blacklisted_guild_detected`` column.

Revision ID: 0008_high_risk_manual_review
Revises: 0007_verification_manual_review
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models.types

revision: str = "0008_high_risk_manual_review"
down_revision: str | Sequence[str] | None = "0007_verification_manual_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""

    op.add_column(
        "verification_attempts",
        sa.Column("matched_high_risk_guild_ids", sa.JSON(), nullable=True),
    )

    # Migrate legacy blacklisted guilds into high-risk guilds. The semantics
    # change from "auto reject" to "manual review trigger"; created_by is
    # unknown for migrated rows (NULL). Existing high-risk entries take
    # precedence via ON CONFLICT DO NOTHING against the owner/target unique key.
    op.execute(
        """
        INSERT INTO guild_high_risk_guilds (
            id,
            guild_id,
            high_risk_discord_guild_id,
            reason,
            created_by,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            guild_id,
            blacklisted_discord_guild_id,
            reason,
            NULL,
            created_at,
            updated_at
        FROM guild_blacklisted_guilds
        ON CONFLICT (guild_id, high_risk_discord_guild_id) DO NOTHING
        """
    )

    op.drop_table("guild_blacklisted_guilds")

    op.drop_column("verification_attempts", "blacklisted_guild_detected")


def downgrade() -> None:
    """Revert this migration.

    Structural revert only: the blacklisted-guild table and column are
    recreated empty. The original blacklist/high-risk split cannot be
    reconstructed from the merged high-risk data, so migrated rows are not
    moved back.
    """

    op.add_column(
        "verification_attempts",
        sa.Column(
            "blacklisted_guild_detected",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )

    op.create_table(
        "guild_blacklisted_guilds",
        sa.Column("guild_id", sa.Uuid(), nullable=False),
        sa.Column(
            "blacklisted_discord_guild_id",
            app.models.types.DiscordSnowflake(length=20),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=200), nullable=True),
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
            name=op.f("fk_guild_blacklisted_guilds_guild_id_guilds"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guild_blacklisted_guilds")),
        sa.UniqueConstraint(
            "guild_id",
            "blacklisted_discord_guild_id",
            name="uq_guild_blacklisted_guilds_owner_target",
        ),
    )

    op.drop_column("verification_attempts", "matched_high_risk_guild_ids")
