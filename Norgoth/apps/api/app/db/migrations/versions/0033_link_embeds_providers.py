"""Remap Link Embeds TikTok host and drop Bluesky JSON keys.

Revision ID: 0033_link_embeds_providers
Revises: 0032_event_log_discord_ids
Create Date: 2026-08-19
"""

from __future__ import annotations

import json
import logging
import os

import sqlalchemy as sa
from alembic import op

from app.services.rich_link_embeds_normalize import (
    disable_tiktok_for_downgrade,
    normalize_rich_link_embeds_config,
    stored_needs_link_embeds_normalize,
)

revision = "0033_link_embeds_providers"
down_revision = "0032_event_log_discord_ids"
branch_labels = None
depends_on = None

logger = logging.getLogger("norgoth.alembic.0033")

_SNAPSHOT_MATCH = "norgoth:guild:*:rich_link_embeds"


def _as_dict(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _refresh_redis_snapshots() -> None:
    """Drop stale Link Embeds Redis snapshots (not :seen: keys)."""

    url = os.getenv("NORGOTH_REDIS_URL", "").strip()
    if not url:
        logger.info("skip redis snapshot refresh: NORGOTH_REDIS_URL unset")
        return
    try:
        import redis as redis_sync
    except ImportError:
        logger.info("skip redis snapshot refresh: redis package missing")
        return
    try:
        client = redis_sync.from_url(url)
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor, match=_SNAPSHOT_MATCH, count=200
            )
            if keys:
                client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        client.close()
        logger.info("deleted %s rich_link_embeds redis snapshots", deleted)
    except Exception:  # noqa: BLE001
        logger.warning("redis snapshot refresh failed", exc_info=True)


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT guild_id, config FROM rich_link_embeds_configs")
    ).mappings()
    for row in rows:
        payload = _as_dict(row["config"])
        if not stored_needs_link_embeds_normalize(payload):
            hosts = payload.get("rewrite_hosts")
            if isinstance(hosts, dict) and hosts.get("tiktok") == "tnktok.com":
                continue
        normalized = normalize_rich_link_embeds_config(payload)
        conn.execute(
            sa.text(
                "UPDATE rich_link_embeds_configs "
                "SET config = CAST(:config AS jsonb), updated_at = now() "
                "WHERE guild_id = :guild_id"
            ),
            {
                "guild_id": row["guild_id"],
                "config": json.dumps(normalized),
            },
        )
    _refresh_redis_snapshots()


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT guild_id, config FROM rich_link_embeds_configs")
    ).mappings()
    for row in rows:
        payload = _as_dict(row["config"])
        rolled = disable_tiktok_for_downgrade(payload)
        conn.execute(
            sa.text(
                "UPDATE rich_link_embeds_configs "
                "SET config = CAST(:config AS jsonb), updated_at = now() "
                "WHERE guild_id = :guild_id"
            ),
            {
                "guild_id": row["guild_id"],
                "config": json.dumps(rolled),
            },
        )
    _refresh_redis_snapshots()
