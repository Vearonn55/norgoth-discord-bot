"""Guild activity monitor — aggregates Redis event streams into one feed."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import ACTIVITY_KEY, get_redis

router = APIRouter(
    tags=["Activity"],
    dependencies=[Depends(guild_manager_dependency())],
)

FETCH_PER_SOURCE = 200


def event_log_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:eventlog"


def moderation_log_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:modlog"


def raid_incidents_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:raid:incidents"


def honeypot_triggers_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:honeypot:triggers"


async def load_list(redis_client, key: str, limit: int = FETCH_PER_SOURCE) -> list[dict[str, Any]]:
    raw_entries = await redis_client.lrange(key, 0, limit - 1)
    items: list[dict[str, Any]] = []

    for raw in raw_entries:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            items.append(parsed)

    return items


def normalize_eventlog(entry: dict[str, Any]) -> dict[str, Any]:
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    return {
        "id": str(entry.get("id") or ""),
        "timestamp": str(entry.get("created_at") or ""),
        "category": "event",
        "event": str(entry.get("action") or entry.get("description") or "event"),
        "actor": str(
            entry.get("actor_name")
            or fields.get("Actor")
            or entry.get("actor_id")
            or ""
        ),
        "channel": str(fields.get("Channel") or fields.get("channel") or ""),
        "result": str(entry.get("description") or ""),
        "severity": entry,
    }


def normalize_modlog(entry: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or f"modlog-{index}"),
        "timestamp": str(entry.get("created_at") or ""),
        "category": "moderation",
        "event": str(entry.get("action") or "moderation"),
        "actor": str(entry.get("moderator_name") or entry.get("moderator_id") or ""),
        "channel": "",
        "result": str(entry.get("detail") or entry.get("reason") or ""),
        "opportunity": {
            "target": entry.get("target"),
            "reason": entry.get("reason"),
            **{k: v for k, v in entry.items() if k not in ("id",)},
        },
    }


def normalize_campaign(entry: dict[str, Any], guild_id: str) -> dict[str, Any] | None:
    # Campaign activity is global; include when guild matches or is unset.
    campaign_guild = entry.get("guild_id")
    if campaign_guild and str(campaign_guild) != str(guild_id):
        return None

    return {
        "id": str(entry.get("id") or ""),
        "timestamp": str(entry.get("created_at") or ""),
        "category": "campaign",
        "event": str(entry.get("type") or "campaign"),
        "actor": str(entry.get("campaign_title") or entry.get("campaign_id") or ""),
        "channel": "",
        "result": str(entry.get("message") or ""),
        "opportunity": entry,
    }


def normalize_raid(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or ""),
        "timestamp": str(entry.get("started_at") or entry.get("created_at") or ""),
        "category": "raid",
        "event": str(entry.get("status") or "raid_incident"),
        "actor": "Raid Protection",
        "channel": str(entry.get("alert_channel_id") or ""),
        "result": (
            f"joins/min={entry.get('joins_per_minute', '?')}, "
            f"young_ratio={entry.get('young_account_ratio', '?')}%"
        ),
        "opportunity": entry,
    }


def normalize_honeypot(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id") or ""),
        "timestamp": str(entry.get("created_at") or ""),
        "category": "honeypot",
        "event": str(entry.get("punishment") or "honeypot_trigger"),
        "actor": str(entry.get("member_name") or entry.get("member_id") or ""),
        "channel": str(entry.get("channel_name") or entry.get("channel_id") or ""),
        "result": str(entry.get("result") or entry.get("detail") or ""),
        "opportunity": entry,
    }


@router.get("/guilds/{guild_id}/activity")
async def get_guild_activity(
    guild_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    category: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        event_entries = await load_list(redis_client, event_log_key(guild_id))
        mod_entries = await load_list(redis_client, moderation_log_key(guild_id))
        campaign_entries = await load_list(redis_client, ACTIVITY_KEY, limit=100)
        raid_entries = await load_list(redis_client, raid_incidents_key(guild_id))
        honeypot_entries = await load_list(
            redis_client, honeypot_triggers_key(guild_id)
        )
    finally:
        await redis_client.aclose()

    items: list[dict[str, Any]] = []

    for entry in event_entries:
        items.append(normalize_eventlog(entry))

    for index, entry in enumerate(mod_entries):
        items.append(normalize_modlog(entry, index))

    for entry in campaign_entries:
        normalized = normalize_campaign(entry, guild_id)
        if normalized is not None:
            items.append(normalized)

    for entry in raid_entries:
        items.append(normalize_raid(entry))

    for entry in honeypot_entries:
        items.append(normalize_honeypot(entry))

    category_filter = (category or "").strip().lower()
    query = (q or "").strip().lower()

    if category_filter:
        items = [
            item for item in items if str(item.get("category", "")).lower() == category_filter
        ]

    if query:
        items = [
            item
            for item in items
            if query in " ".join(
                str(item.get(field) or "")
                for field in ("event", "actor", "channel", "result", "category")
            ).lower()
        ]

    items.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)

    total = len(items)
    page = items[offset : offset + limit]

    return {
        "guild_id": guild_id,
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit,
    }
