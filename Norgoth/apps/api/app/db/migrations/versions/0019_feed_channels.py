"""Feed Channels tables + feed_configs feature snapshot.

Revision ID: 0019_feed_channels
Revises: 0018_drop_invite_logging_configs
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_feed_channels"
down_revision: str | Sequence[str] | None = "0018_drop_invite_logging_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feed_configs",
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_object()"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_configs")),
        sa.UniqueConstraint("guild_id", name=op.f("uq_feed_configs_guild_id")),
    )

    op.create_table(
        "feed_messages",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=32), nullable=False),
        sa.Column("author_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_excerpt", sa.String(length=500), nullable=True),
        sa.Column(
            "attachment_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "upvote_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "downvote_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "net_score",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "row_created_at",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_messages")),
        sa.UniqueConstraint(
            "guild_id",
            "message_id",
            name="uq_feed_messages_guild_message",
        ),
    )
    op.create_index(
        "ix_feed_messages_guild_rank",
        "feed_messages",
        ["guild_id", "status", "net_score", "upvote_count", "created_at", "message_id"],
    )
    op.create_index(
        "ix_feed_messages_guild_created",
        "feed_messages",
        ["guild_id", "created_at"],
    )
    op.create_index(
        "ix_feed_messages_guild_author",
        "feed_messages",
        ["guild_id", "author_id"],
    )

    op.create_table(
        "feed_votes",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=32), nullable=False),
        sa.Column("voter_id", sa.String(length=32), nullable=False),
        sa.Column("vote", sa.String(length=8), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_votes")),
        sa.UniqueConstraint(
            "guild_id",
            "message_id",
            "voter_id",
            name="uq_feed_votes_guild_message_voter",
        ),
    )
    op.create_index(
        "ix_feed_votes_guild_message",
        "feed_votes",
        ["guild_id", "message_id"],
    )

    op.create_table(
        "feed_entries",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("window", sa.String(length=16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("feed_channel_id", sa.String(length=32), nullable=False),
        sa.Column("feed_message_id", sa.String(length=32), nullable=False),
        sa.Column("source_message_id", sa.String(length=32), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_entries")),
        sa.UniqueConstraint(
            "guild_id",
            "window",
            "rank",
            name="uq_feed_entries_guild_window_rank",
        ),
        sa.UniqueConstraint(
            "guild_id",
            "feed_message_id",
            name="uq_feed_entries_guild_feed_message",
        ),
    )
    op.create_index(
        "ix_feed_entries_guild_window",
        "feed_entries",
        ["guild_id", "window"],
    )

    op.create_table(
        "feed_author_stats",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column(
            "net_score",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "upvote_total",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "downvote_total",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "post_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_author_stats")),
        sa.UniqueConstraint(
            "guild_id",
            "user_id",
            name="uq_feed_author_stats_guild_user",
        ),
    )
    op.create_index(
        "ix_feed_author_stats_guild_net",
        "feed_author_stats",
        ["guild_id", "net_score"],
    )


def downgrade() -> None:
    op.drop_table("feed_author_stats")
    op.drop_table("feed_entries")
    op.drop_table("feed_votes")
    op.drop_table("feed_messages")
    op.drop_table("feed_configs")
