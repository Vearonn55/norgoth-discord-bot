"""Per-guild Link Embeds configuration (clean-room NorBot feature).

User-facing name: Link Embeds / Bağlantı Önizlemeleri.
Internal key/route remains ``rich_link_embeds`` for compatibility.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config
from app.services.rich_link_embeds_normalize import (
    DEFAULT_REWRITE_HOSTS,
    normalize_rich_link_embeds_config,
    stored_needs_link_embeds_normalize,
)

router = APIRouter(
    tags=["Link Embeds"],
    dependencies=[Depends(guild_manager_dependency())],
)

class PlatformToggles(BaseModel):
    twitter: bool = True
    tiktok: bool = True
    reddit: bool = True
    # New platforms default off so existing guilds do not suddenly rewrite.
    instagram: bool = False
    pixiv: bool = False
    youtube_shorts: bool = False


class RewriteHosts(BaseModel):
    twitter: str = "fxtwitter.com"
    tiktok: str = "tnktok.com"
    instagram: str = "instagram7.com"
    reddit: str = "vxreddit.com"
    pixiv: str = "phixiv.net"
    youtube_shorts: str = "youtu.be"


class RichLinkEmbedsConfigBody(BaseModel):
    enabled: bool = False
    platforms: PlatformToggles = Field(default_factory=PlatformToggles)
    channel_allowlist: list[str] = Field(default_factory=list, max_length=50)
    channel_denylist: list[str] = Field(default_factory=list, max_length=50)
    ignore_bots: bool = True
    process_edits: bool = False
    max_links_per_message: int = Field(default=3, ge=1, le=10)
    rewrite_hosts: RewriteHosts = Field(default_factory=RewriteHosts)
    disclosure_acknowledged: bool = False


def _snowflake_list(values: list[str]) -> list[str]:
    return [
        value
        for value in values
        if isinstance(value, str) and value.isdigit() and 5 <= len(value) <= 25
    ]


def load_stored_config(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _force_allowlisted_hosts(_incoming: dict[str, Any] | None = None) -> dict[str, str]:
    """Always return the fixed operator allowlist (ignore client overrides)."""

    return dict(DEFAULT_REWRITE_HOSTS)


@router.get("/guilds/{guild_id}/rich-link-embeds")
async def get_rich_link_embeds_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()
    try:
        raw = await read_raw(guild_id, "rich_link_embeds", redis_client)
    finally:
        await redis_client.aclose()

    stored = load_stored_config(raw)
    if stored_needs_link_embeds_normalize(stored):
        stored = normalize_rich_link_embeds_config(stored)
        stored["rewrite_hosts"] = _force_allowlisted_hosts()
        stored["updated_at"] = now_iso()
        await save_config(
            guild_id,
            "rich_link_embeds",
            stored,
            enabled=bool(stored.get("enabled", False)),
        )
    config = RichLinkEmbedsConfigBody.model_validate(
        {k: v for k, v in stored.items() if k in RichLinkEmbedsConfigBody.model_fields}
        or {}
    )
    payload = config.model_dump()
    payload["rewrite_hosts"] = _force_allowlisted_hosts()
    return {"guild_id": guild_id, **payload}


@router.put("/guilds/{guild_id}/rich-link-embeds")
async def update_rich_link_embeds_config(
    guild_id: str,
    body: RichLinkEmbedsConfigBody,
) -> dict[str, Any]:
    redis_client = await get_redis()
    try:
        payload = body.model_dump()
        payload["channel_allowlist"] = _snowflake_list(payload["channel_allowlist"])
        payload["channel_denylist"] = _snowflake_list(payload["channel_denylist"])
        # Guild admins cannot choose arbitrary redirect targets.
        payload["rewrite_hosts"] = _force_allowlisted_hosts()
        payload["updated_at"] = now_iso()
        await save_config(
            guild_id,
            "rich_link_embeds",
            payload,
            enabled=bool(payload.get("enabled", False)),
        )
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, **payload}
