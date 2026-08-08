"""Deduplicate logging rows and enforce per-config uniqueness.

Rapid enable/disable toggling previously ran a delete-all-then-recreate under
concurrency, which could duplicate logging_channels and logging_event_mappings
rows. This migration removes any accumulated duplicates (keeping one row per
natural key) and adds the unique constraints that make the write idempotent.

Revision ID: 0006_logging_uniqueness
Revises: 0005_embed_sync
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_logging_uniqueness"
down_revision: str | None = "0005_embed_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Dedupe channels: keep a single row per (configuration, key). ctid is a
    # stable physical row identifier, so "> b.ctid" keeps the earliest row.
    op.execute(
        """
        DELETE FROM logging_channels a
        USING logging_channels b
        WHERE a.logging_configuration_id = b.logging_configuration_id
          AND a.key = b.key
          AND a.ctid > b.ctid
        """
    )
    # Dedupe event mappings: keep a single row per (configuration, event_type).
    op.execute(
        """
        DELETE FROM logging_event_mappings a
        USING logging_event_mappings b
        WHERE a.logging_configuration_id = b.logging_configuration_id
          AND a.event_type = b.event_type
          AND a.ctid > b.ctid
        """
    )

    op.create_unique_constraint(
        "uq_logging_channels_config_key",
        "logging_channels",
        ["logging_configuration_id", "key"],
    )
    op.create_unique_constraint(
        "uq_logging_event_mappings_config_event",
        "logging_event_mappings",
        ["logging_configuration_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_logging_event_mappings_config_event",
        "logging_event_mappings",
        type_="unique",
    )
    op.drop_constraint(
        "uq_logging_channels_config_key",
        "logging_channels",
        type_="unique",
    )
