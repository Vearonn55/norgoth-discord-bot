"""Per-guild Rich Link Embeds configuration (clean-room NorBot feature)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

router = APIRouter(
    tags=["Rich Link Embeds"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

DEFAULT_REWRITE_HOSTS = {
    "twitter": "fxtwitter.com",
    "bluesky": "bskx.app",
    "tiktok": "vxtiktok.com",
    "reddit": "vxreddit.com",
}


class PlatformToggles(BaseModel):
    twitter: bool = True
    bluesky: bool = True
    tiktok: bool = True
    reddit: bool = True


class RewriteHosts(BaseModel):
    twitter: str = "fxtwitter.com"
    bluesky: str = "bskx.app"
    tiktok: str = "vxtiktok.com"
    reddit: str = "vxreddit.com"


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


@router.get("/guilds/{guild_id}/rich-link-embeds")
async def get_rich_link_embeds_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()
    try:
        raw = await read_raw(guild_id, "rich_link_embeds", redis_client)
    finally:
        await redis_client.aclose()

    stored = load_stored_config(raw)
    config = RichLinkEmbedsConfigBody.model_validate(
        {k: v for k, v in stored.items() if k in RichLinkEmbedsConfigBody.model_fields}
        or {}
    )
    return {"guild_id": guild_id, **config.model_dump()}


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
        # Never accept empty rewrite hosts — fall back to defaults.
        hosts = payload.get("rewrite_hosts") or {}
        for key, default in DEFAULT_REWRITE_HOSTS.items():
            host = str(hosts.get(key) or "").strip().lower()
            hosts[key] = host or default
        payload["rewrite_hosts"] = hosts
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
