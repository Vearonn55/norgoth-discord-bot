"""Guild metadata for public verification pages (name + icon hash)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.integrations.discord.cdn import discord_icon_url
from app.services.campaign_store import get_redis

logger = logging.getLogger(__name__)

META_TTL_SECONDS = 3600
META_KEY_PREFIX = "norgoth:guild:"


@dataclass(frozen=True, slots=True)
class GuildPublicMeta:
    """Safe public identity for a Discord guild."""

    guild_id: str
    name: str
    icon_hash: str | None
    icon_url: str | None


def _meta_key(guild_id: str) -> str:
    return f"{META_KEY_PREFIX}{guild_id}:meta"


def guild_initials(name: str) -> str:
    parts = name.strip().split()
    letters = [part[0] for part in parts[:2] if part]
    return "".join(letters).upper() or "?"


async def resolve_guild_public_meta(
    *,
    discord_guild_id: str,
    fallback_name: str,
    bot_client: DiscordBotClient | None,
) -> GuildPublicMeta:
    """Resolve live Discord name/icon, with Redis cache and PG name fallback."""

    cached = await _read_cache(discord_guild_id)
    if cached is not None:
        return cached

    name = fallback_name or "this server"
    icon_hash: str | None = None

    if bot_client is not None:
        try:
            payload = await bot_client.get_guild(discord_guild_id)
            live_name = payload.get("name")
            if isinstance(live_name, str) and live_name.strip():
                name = live_name.strip()
            raw_icon = payload.get("icon")
            if isinstance(raw_icon, str) and raw_icon:
                icon_hash = raw_icon
        except DiscordBotAPIError:
            logger.info(
                "Guild metadata unavailable for %s",
                discord_guild_id,
                exc_info=True,
            )

    meta = GuildPublicMeta(
        guild_id=str(discord_guild_id),
        name=name,
        icon_hash=icon_hash,
        icon_url=discord_icon_url(str(discord_guild_id), icon_hash, size=128),
    )
    await _write_cache(meta)
    return meta


async def invalidate_guild_public_meta(discord_guild_id: str) -> None:
    try:
        redis_client = await get_redis()
        try:
            await redis_client.delete(_meta_key(discord_guild_id))
        finally:
            await redis_client.aclose()
    except Exception:
        logger.debug("Could not invalidate guild meta cache", exc_info=True)


async def _read_cache(guild_id: str) -> GuildPublicMeta | None:
    try:
        redis_client = await get_redis()
        try:
            raw = await redis_client.get(_meta_key(guild_id))
        finally:
            await redis_client.aclose()
    except Exception:
        return None

    if not raw:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        name = str(data.get("name") or "").strip() or "this server"
        icon_hash = data.get("icon")
        if icon_hash is not None:
            icon_hash = str(icon_hash) or None
        return GuildPublicMeta(
            guild_id=str(guild_id),
            name=name,
            icon_hash=icon_hash,
            icon_url=discord_icon_url(str(guild_id), icon_hash, size=128),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


async def _write_cache(meta: GuildPublicMeta) -> None:
    try:
        redis_client = await get_redis()
        try:
            payload = json.dumps(
                {"name": meta.name, "icon": meta.icon_hash},
                separators=(",", ":"),
            )
            await redis_client.set(
                _meta_key(meta.guild_id),
                payload,
                ex=META_TTL_SECONDS,
            )
        finally:
            await redis_client.aclose()
    except Exception:
        logger.debug("Could not write guild meta cache", exc_info=True)
