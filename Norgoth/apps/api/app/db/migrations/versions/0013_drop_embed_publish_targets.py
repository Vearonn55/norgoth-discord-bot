"""Drop draft-owned embed publish targets.

Embed drafts are now content-only: deployment destinations are owned by the
Deploy action or by consuming features, tracked as ``embed_message_deliveries``.
The draft-owned ``embed_messages.target_channel_ids`` column and the
``embed_message_channel_targets`` mirror table are no longer read by any code
path and are removed here. Existing real deployments are unaffected.

Revision ID: 0013_drop_embed_publish_targets
Revises: 0012_embed_deployment_owner
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_drop_embed_publish_targets"
down_revision: str | Sequence[str] | None = "0012_embed_deployment_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""

    op.drop_index(
        "ix_embed_message_channel_targets_guild_id",
        table_name="embed_message_channel_targets",
    )
    op.drop_table("embed_message_channel_targets")
    op.drop_column("embed_messages", "target_channel_ids")


def downgrade() -> None:
    """Revert this migration (structure only; data is not restored)."""

    op.add_column(
        "embed_messages",
        sa.Column(
            "target_channel_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_table(
        "embed_message_channel_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embed_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
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
            ["embed_message_id"],
            ["embed_messages.id"],
            name=op.f(
                "fk_embed_message_channel_targets_embed_message_id_embed_messages"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_embed_message_channel_targets")
        ),
        sa.UniqueConstraint(
            "embed_message_id",
            "channel_id",
            name="uq_embed_message_channel_targets_message_channel",
        ),
    )
    op.create_index(
        "ix_embed_message_channel_targets_guild_id",
        "embed_message_channel_targets",
        ["guild_id"],
        unique=False,
    )
