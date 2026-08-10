"""Add owner_feature to embed message deliveries.

Deployments (sent Discord messages tracked as ``embed_message_deliveries``) now
record which Norgoth feature owns them. Generic Re-Sync may recreate a missing
message only for ``embed_library``-owned deployments; feature-owned ones (e.g.
Self-Assignable Roles) require components and are flagged for feature repair
instead. Existing rows default to ``embed_library``; role-menu bound deliveries
are re-stamped to ``self_assignable_role`` at runtime (and by an optional
backfill script).

Revision ID: 0012_embed_deployment_owner
Revises: 0011_drop_verified_role
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_embed_deployment_owner"
down_revision: str | Sequence[str] | None = "0011_drop_verified_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""

    op.add_column(
        "embed_message_deliveries",
        sa.Column(
            "owner_feature",
            sa.String(length=32),
            nullable=True,
            server_default="embed_library",
        ),
    )
    # Backfill any pre-existing rows, then drop the server default so the ORM
    # default governs new rows.
    op.execute(
        "UPDATE embed_message_deliveries "
        "SET owner_feature = 'embed_library' WHERE owner_feature IS NULL"
    )
    op.alter_column(
        "embed_message_deliveries",
        "owner_feature",
        server_default=None,
    )


def downgrade() -> None:
    """Revert this migration."""

    op.drop_column("embed_message_deliveries", "owner_feature")
