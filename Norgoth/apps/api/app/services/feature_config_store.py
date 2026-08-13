"""Write-through config store: Postgres source of truth + Redis snapshot.

Config routes call :func:`save_config` to persist the canonical snapshot payload
to Postgres and rewrite the byte-compatible Redis key the bot reads, and
:func:`read_through` to serve config (Redis cache, rehydrated from Postgres on a
miss). This keeps the bot's Redis read contract identical while making Postgres
the durable source of truth that survives a Redis flush.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.feature_configs import (
    AutomodConfig,
    AutoresponderConfig,
    FeedConfig,
    HoneypotConfig,
    LevelingConfig,
    ModuleConfig,
    RaidConfig,
    RichLinkEmbedsConfig,
    RoleMenuConfig,
    TicketConfig,
    TicketPanelsConfig,
    WelcomeConfig,
)
from app.services.snapshot_writer import get_redis, guild_key, write_snapshot

# feature_key -> (model, redis snapshot suffix)
FEATURE_REGISTRY: dict[str, tuple[type, str]] = {
    "modules": (ModuleConfig, "modules"),
    "automation": (WelcomeConfig, "automation"),
    "automod": (AutomodConfig, "automod"),
    "raid": (RaidConfig, "raid"),
    "honeypot": (HoneypotConfig, "honeypot"),
    "leveling": (LevelingConfig, "leveling:config"),
    "autoresponder": (AutoresponderConfig, "autoresponses"),
    "rolemenus": (RoleMenuConfig, "rolemenus"),
    "tickets": (TicketConfig, "tickets:config"),
    "ticket_panels": (TicketPanelsConfig, "tickets:panels"),
    "feed_channels": (FeedConfig, "feed:config"),
    "rich_link_embeds": (RichLinkEmbedsConfig, "rich_link_embeds"),
}


def snapshot_suffix(feature_key: str) -> str:
    """Return the Redis snapshot suffix for a feature."""

    return FEATURE_REGISTRY[feature_key][1]


async def load_config(guild_id: str, feature_key: str) -> Any | None:
    """Return the durable config payload from Postgres, or ``None``."""

    model, _suffix = FEATURE_REGISTRY[feature_key]
    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(select(model).where(model.guild_id == guild_id))
        ).scalar_one_or_none()
        if row is None or row.config is None:
            return None
        return row.config


async def save_config(
    guild_id: str,
    feature_key: str,
    payload: Any,
    *,
    enabled: bool | None = None,
) -> None:
    """Persist ``payload`` to Postgres, then rewrite the Redis snapshot."""

    model, suffix = FEATURE_REGISTRY[feature_key]

    resolved_enabled = enabled
    if resolved_enabled is None and isinstance(payload, dict):
        resolved_enabled = bool(payload.get("enabled", False))

    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(select(model).where(model.guild_id == guild_id))
        ).scalar_one_or_none()
        if row is None:
            row = model(
                guild_id=guild_id,
                config=payload,
                enabled=bool(resolved_enabled),
            )
            session.add(row)
        else:
            row.config = payload
            row.enabled = bool(resolved_enabled)
        await session.commit()

    await write_snapshot(guild_id, suffix, payload)


async def read_raw(guild_id: str, feature_key: str, redis_client: Any) -> str | None:
    """Return the raw JSON string for a config, hydrating Redis from Postgres.

    Drop-in replacement for ``await redis_client.get(<config_key>)`` so callers
    can keep their existing ``json.loads(raw)`` parsing while gaining a durable
    Postgres backing that survives a Redis flush.
    """

    _model, suffix = FEATURE_REGISTRY[feature_key]
    key = guild_key(guild_id, suffix)

    raw = await redis_client.get(key)
    if raw:
        return raw

    payload = await load_config(guild_id, feature_key)
    if payload is None:
        return None

    serialized = json.dumps(payload)
    await redis_client.set(key, serialized)
    return serialized


async def read_through(guild_id: str, feature_key: str, redis_client: Any) -> Any | None:
    """Return config from Redis; on a miss, hydrate from Postgres and cache it.

    Returns the parsed JSON value (dict/list) or ``None`` when neither Redis nor
    Postgres has the config yet.
    """

    _model, suffix = FEATURE_REGISTRY[feature_key]
    key = guild_key(guild_id, suffix)

    raw = await redis_client.get(key)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    payload = await load_config(guild_id, feature_key)
    if payload is None:
        return None

    await redis_client.set(key, json.dumps(payload))
    return payload
