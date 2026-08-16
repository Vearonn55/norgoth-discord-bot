"""Invite tracking: inviter leaderboard and recent joins with attribution."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis

router = APIRouter(
    tags=["Invites"],
    dependencies=[Depends(guild_manager_dependency())],
)


def invite_counters_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:invites:counters"


def invite_recent_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:invites:recent"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


def _member_display_name(snapshot: dict[str, Any] | None, user_id: str | None) -> str | None:
    if not snapshot or not user_id:
        return None
    members = snapshot.get("members")
    if not isinstance(members, list):
        return None
    for member in members:
        if not isinstance(member, dict):
            continue
        if str(member.get("id")) != str(user_id):
            continue
        return str(
            member.get("display_name")
            or member.get("global_name")
            or member.get("name")
            or user_id
        )
    return None


@router.get("/guilds/{guild_id}/invites/leaderboard")
async def get_invite_leaderboard(guild_id: str) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        counters = await redis_client.hgetall(invite_counters_key(guild_id))
        members_raw = await redis_client.get(guild_members_key(guild_id))
    finally:
        await redis_client.aclose()

    members_snapshot = None
    if members_raw:
        try:
            parsed = json.loads(members_raw)
            if isinstance(parsed, dict):
                members_snapshot = parsed
        except json.JSONDecodeError:
            members_snapshot = None

    leaderboard: list[dict[str, Any]] = []

    for inviter_id, raw in counters.items():
        try:
            counter = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(counter, dict):
            continue

        joins = int(counter.get("joins", 0))
        leaves = int(counter.get("leaves", 0))
        live_name = _member_display_name(members_snapshot, str(inviter_id))

        leaderboard.append(
            {
                "inviter_id": str(inviter_id),
                "name": str(live_name or counter.get("name") or inviter_id),
                "joins": joins,
                "leaves": leaves,
                "rejoins": int(counter.get("rejoins", 0)),
                "net": max(0, joins - leaves),
            }
        )

    leaderboard.sort(key=lambda entry: entry["net"], reverse=True)

    for index, entry in enumerate(leaderboard, start=1):
        entry["rank"] = index

    return leaderboard


@router.get("/guilds/{guild_id}/invites/recent")
async def get_recent_joins(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        raw_entries = await redis_client.lrange(
            invite_recent_key(guild_id),
            0,
            limit - 1,
        )
        members_raw = await redis_client.get(guild_members_key(guild_id))
    finally:
        await redis_client.aclose()

    members_snapshot = None
    if members_raw:
        try:
            parsed = json.loads(members_raw)
            if isinstance(parsed, dict):
                members_snapshot = parsed
        except json.JSONDecodeError:
            members_snapshot = None

    entries: list[dict[str, Any]] = []

    for raw in raw_entries:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(parsed, dict):
            continue
        inviter_id = parsed.get("inviter_id")
        live_name = _member_display_name(
            members_snapshot, str(inviter_id) if inviter_id else None
        )
        if live_name:
            parsed["inviter_name"] = live_name
        parsed.setdefault("attribution", None)
        if not parsed.get("attribution"):
            if parsed.get("code") == "vanity":
                parsed["attribution"] = "vanity"
            elif parsed.get("inviter_id"):
                parsed["attribution"] = "attributed"
            else:
                parsed["attribution"] = "unknown"
        entries.append(parsed)

    return entries
