"""Guild engagement time-series from Redis daily analytics buckets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis
import json

router = APIRouter(
    tags=["Analytics"],
    dependencies=[Depends(guild_manager_dependency())],
)

RangeLiteral = Literal[7, 30, 90]


def daily_key(guild_id: str, day: str) -> str:
    return f"norgoth:guild:{guild_id}:analytics:daily:{day}"


def _day_list(days: int, *, end: datetime | None = None) -> list[str]:
    end = end or datetime.now(timezone.utc)
    return [
        (end - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(days - 1, -1, -1)
    ]


def _empty_point(day: str) -> dict[str, Any]:
    return {
        "date": day,
        "messages": 0,
        "unique_authors": 0,
        "joins": 0,
        "leaves": 0,
        "voice_uniques": 0,
        "has_data": False,
    }


async def _load_series(
    redis_client: Any,
    guild_id: str,
    days: list[str],
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for day in days:
        raw = await redis_client.hgetall(daily_key(guild_id, day))
        if not raw:
            series.append(_empty_point(day))
            continue
        series.append(
            {
                "date": day,
                "messages": int(raw.get("messages") or 0),
                "unique_authors": int(raw.get("unique_authors") or 0),
                "joins": int(raw.get("joins") or 0),
                "leaves": int(raw.get("leaves") or 0),
                "voice_uniques": int(raw.get("voice_uniques") or 0),
                "has_data": True,
            }
        )
    return series


def _sum_totals(series: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "messages": sum(p["messages"] for p in series),
        "unique_authors": sum(p["unique_authors"] for p in series),
        "joins": sum(p["joins"] for p in series),
        "leaves": sum(p["leaves"] for p in series),
        "voice_uniques": sum(p["voice_uniques"] for p in series),
        "days_with_data": sum(1 for p in series if p["has_data"]),
    }


@router.get("/guilds/{guild_id}/analytics/engagement")
async def get_engagement(
    guild_id: str,
    range: int = Query(default=7, alias="range"),
) -> dict[str, Any]:
    if range not in (7, 30, 90):
        raise HTTPException(status_code=400, detail="range must be 7, 30, or 90")

    now = datetime.now(timezone.utc)
    current_days = _day_list(range, end=now)
    previous_end = now - timedelta(days=range)
    previous_days = _day_list(range, end=previous_end)

    redis_client = await get_redis()
    try:
        series = await _load_series(redis_client, guild_id, current_days)
        previous_series = await _load_series(redis_client, guild_id, previous_days)
    finally:
        await redis_client.aclose()

    totals = _sum_totals(series)
    previous_totals = _sum_totals(previous_series)

    return {
        "guild_id": guild_id,
        "range": range,
        "series": series,
        "totals": totals,
        "previous_totals": previous_totals,
        "insufficient_history": totals["days_with_data"] == 0,
    }


@router.get("/guilds/{guild_id}/analytics/security")
async def get_security_analytics(
    guild_id: str,
    range: int = Query(default=30, alias="range"),
) -> dict[str, Any]:
    """Compact security metrics for raid + honeypot (no dashboard KPI flood)."""

    if range not in (7, 30, 90):
        raise HTTPException(status_code=400, detail="range must be 7, 30, or 90")

    redis_client = await get_redis()
    try:
        raid_raw = await redis_client.lrange(
            f"norgoth:guild:{guild_id}:raid:incidents", 0, 499
        )
        honey_raw = await redis_client.lrange(
            f"norgoth:guild:{guild_id}:honeypot:triggers", 0, 499
        )
        active = await redis_client.get(f"norgoth:guild:{guild_id}:raid:incident")
    finally:
        await redis_client.aclose()

    cutoff = datetime.now(timezone.utc) - timedelta(days=range)

    def _parse_list(raw_entries: list) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for raw in raw_entries:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        return items

    raids = _parse_list(raid_raw)
    triggers = _parse_list(honey_raw)

    def _in_range(item: dict[str, Any], keys: tuple[str, ...]) -> bool:
        for key in keys:
            value = item.get(key)
            if not value:
                continue
            try:
                ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
            return ts >= cutoff
        return True

    raids_in_range = [
        item for item in raids if _in_range(item, ("started_at", "start_time", "created_at"))
    ]
    triggers_in_range = [
        item
        for item in triggers
        if _in_range(item, ("triggered_at", "created_at"))
    ]

    punishments = sum(
        1
        for item in triggers_in_range
        if str(item.get("punishment_status") or item.get("result") or "").lower()
        in {"ok", "success", "applied", "banned", "kicked", "timed_out", "deleted"}
    )

    return {
        "guild_id": guild_id,
        "range": range,
        "raid_incidents": len(raids_in_range),
        "honeypot_triggers": len(triggers_in_range),
        "honeypot_punishments": punishments,
        "active_raid": bool(active),
        "peak_join_rate": max(
            (
                int(item.get("peak_join_rate") or 0)
                for item in raids_in_range
            ),
            default=0,
        ),
    }
