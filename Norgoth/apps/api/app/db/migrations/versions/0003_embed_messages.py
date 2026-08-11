"""Create embed message, media asset, and delivery tables.

Revision ID: 0003_embed_messages
Revises: 0002_content_notifications
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_embed_messages"
down_revision: str | None = "0002_content_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embed_media_assets",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("public_url", sa.String(length=600), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_embed_media_assets"),
    )
    op.create_index(
        "ix_embed_media_assets_guild_id",
        "embed_media_assets",
        ["guild_id"],
    )

    op.create_table(
        "embed_messages",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "embed_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
        sa.PrimaryKeyConstraint("id", name="pk_embed_messages"),
    )
    op.create_index(
        "ix_embed_messages_guild_id",
        "embed_messages",
        ["guild_id"],
    )

    op.create_table(
        "embed_message_deliveries",
        sa.Column("embed_message_id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
        sa.Column("discord_message_id", sa.String(length=32), nullable=True),
        sa.Column(
            "delivery_type",
            sa.String(length=16),
            server_default="bot",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
            ["embed_message_id"],
            ["embed_messages.id"],
            name="fk_embed_delivery_message_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_embed_message_deliveries"),
    )
    op.create_index(
        "ix_embed_message_deliveries_guild_id",
        "embed_message_deliveries",
        ["guild_id"],
    )
    op.create_index(
        "ix_embed_message_deliveries_message",
        "embed_message_deliveries",
        ["embed_message_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_embed_message_deliveries_message",
        table_name="embed_message_deliveries",
    )
    op.drop_index(
        "ix_embed_message_deliveries_guild_id",
        table_name="embed_message_deliveries",
    )
    op.drop_table("embed_message_deliveries")

    op.drop_index("ix_embed_messages_guild_id", table_name="embed_messages")
    op.drop_table("embed_messages")

    op.drop_index("ix_embed_media_assets_guild_id", table_name="embed_media_assets")
    op.drop_table("embed_media_assets")
