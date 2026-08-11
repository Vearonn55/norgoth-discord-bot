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


def authors_key(guild_id: str, day: str) -> str:
    return f"norgoth:guild:{guild_id}:analytics:authors:{day}"


def voice_key(guild_id: str, day: str) -> str:
    return f"norgoth:guild:{guild_id}:analytics:voice:{day}"


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
        "rejoins": 0,
        "leaves": 0,
        "voice_uniques": 0,
        # Total member population recorded that day (last write wins). None when
        # the bot recorded no snapshot for the day (e.g. it was offline).
        "member_count": None,
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
        member_count_raw = raw.get("member_count")
        series.append(
            {
                "date": day,
                "messages": int(raw.get("messages") or 0),
                "unique_authors": int(raw.get("unique_authors") or 0),
                "joins": int(raw.get("joins") or 0),
                "rejoins": int(raw.get("rejoins") or 0),
                "leaves": int(raw.get("leaves") or 0),
                "voice_uniques": int(raw.get("voice_uniques") or 0),
                "member_count": (
                    int(member_count_raw) if member_count_raw is not None else None
                ),
                "has_data": True,
            }
        )
    return series


def _population_metrics(series: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive population-based KPIs from the per-day member_count snapshots.

    Net growth is measured from the actual population delta (end minus start of
    the window) rather than ``joins - leaves`` so it reflects reality even when
    the bot missed some events. Rejoins are intentionally excluded from
    "new members"; they still move the population and therefore show up in the
    snapshot-derived net change.

    Churn and retention are normalized against the starting population so they
    are comparable across servers of different sizes. All fields are ``None``
    when there are no member_count snapshots in the window (insufficient data).
    """

    counts = [p["member_count"] for p in series if p.get("member_count") is not None]
    leaves = sum(p["leaves"] for p in series)
    joins = sum(p["joins"] for p in series)

    if not counts:
        return {
            "start_members": None,
            "end_members": None,
            "net_member_change": None,
            "net_growth_rate": None,
            "churn_rate": None,
            "retention_rate": None,
            "new_members": joins,
        }

    start_members = counts[0]
    end_members = counts[-1]
    net_member_change = end_members - start_members
    net_growth_rate = net_member_change / start_members if start_members else None
    churn_rate = leaves / start_members if start_members else None
    retention_rate = (
        max(0.0, 1.0 - churn_rate) if churn_rate is not None else None
    )

    return {
        "start_members": start_members,
        "end_members": end_members,
        "net_member_change": net_member_change,
        "net_growth_rate": net_growth_rate,
        "churn_rate": churn_rate,
        "retention_rate": retention_rate,
        # First-time joins only (rejoins excluded), for the "new members" KPI.
        "new_members": joins,
    }


async def _distinct_count(redis_client: Any, keys: list[str]) -> int:
    """Return the number of distinct members across the given day sets.

    Uses SUNION so members active on multiple days are counted once (a true
    window-distinct count), unlike summing each day's per-day distinct count.
    Missing/expired day sets are treated as empty.
    """
    if not keys:
        return 0
    members = await redis_client.sunion(keys)
    return len(members)


async def _compute_totals(
    redis_client: Any,
    guild_id: str,
    days: list[str],
    series: list[dict[str, Any]],
) -> dict[str, int]:
    unique_authors = await _distinct_count(
        redis_client, [authors_key(guild_id, day) for day in days]
    )
    voice_uniques = await _distinct_count(
        redis_client, [voice_key(guild_id, day) for day in days]
    )
    return {
        # Counting events is additive over the window.
        "messages": sum(p["messages"] for p in series),
        "joins": sum(p["joins"] for p in series),
        "rejoins": sum(p["rejoins"] for p in series),
        "leaves": sum(p["leaves"] for p in series),
        # Distinct members are unioned across the window, not summed per-day.
        "unique_authors": unique_authors,
        "voice_uniques": voice_uniques,
        "days_with_data": sum(1 for p in series if p["has_data"]),
        # Snapshot-derived population KPIs (net growth, churn, retention).
        **_population_metrics(series),
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
        totals = await _compute_totals(
            redis_client, guild_id, current_days, series
        )
        previous_totals = await _compute_totals(
            redis_client, guild_id, previous_days, previous_series
        )
    finally:
        await redis_client.aclose()

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
