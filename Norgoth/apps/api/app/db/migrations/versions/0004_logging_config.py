"""Create logging configuration tables and embed target_channel_ids.

Revision ID: 0004_logging_config
Revises: 0003_embed_messages
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_logging_config"
down_revision: str | None = "0003_embed_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "embed_messages",
        sa.Column(
            "target_channel_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.create_table(
        "logging_configurations",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "status", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("category_id", sa.String(length=32), nullable=True),
        sa.Column("category_name", sa.String(length=100), nullable=True),
        sa.Column(
            "norgoth_managed_category",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=32), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_logging_configurations"),
    )
    op.create_index(
        "ux_logging_configurations_guild_id",
        "logging_configurations",
        ["guild_id"],
        unique=True,
    )

    op.create_table(
        "logging_channels",
        sa.Column("logging_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("channel_id", sa.String(length=32), nullable=True),
        sa.Column(
            "norgoth_managed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("default_color", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
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
            ["logging_configuration_id"],
            ["logging_configurations.id"],
            name="fk_logging_channel_config_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_logging_channels"),
    )
    op.create_index(
        "ix_logging_channels_config",
        "logging_channels",
        ["logging_configuration_id"],
    )
    op.create_index(
        "ix_logging_channels_guild_id",
        "logging_channels",
        ["guild_id"],
    )

    op.create_table(
        "logging_event_mappings",
        sa.Column("logging_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("logging_channel_id", sa.Uuid(), nullable=True),
        sa.Column("color", sa.Integer(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.true(), nullable=False
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
            ["logging_configuration_id"],
            ["logging_configurations.id"],
            name="fk_logging_event_config_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["logging_channel_id"],
            ["logging_channels.id"],
            name="fk_logging_event_channel_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_logging_event_mappings"),
    )
    op.create_index(
        "ix_logging_event_mappings_config",
        "logging_event_mappings",
        ["logging_configuration_id"],
    )
    op.create_index(
        "ix_logging_event_mappings_guild_id",
        "logging_event_mappings",
        ["guild_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_logging_event_mappings_guild_id",
        table_name="logging_event_mappings",
    )
    op.drop_index(
        "ix_logging_event_mappings_config",
        table_name="logging_event_mappings",
    )
    op.drop_table("logging_event_mappings")

    op.drop_index("ix_logging_channels_guild_id", table_name="logging_channels")
    op.drop_index("ix_logging_channels_config", table_name="logging_channels")
    op.drop_table("logging_channels")

    op.drop_index(
        "ux_logging_configurations_guild_id",
        table_name="logging_configurations",
    )
    op.drop_table("logging_configurations")

    op.drop_column("embed_messages", "target_channel_ids")
