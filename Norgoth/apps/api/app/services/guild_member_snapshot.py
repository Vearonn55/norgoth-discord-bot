"""Helpers for guild member snapshots stored in Redis by the bot."""

from __future__ import annotations

import math
from typing import Any


def member_sort_key(member: dict[str, Any]) -> tuple[str, str]:
    label = str(
        member.get("display_name") or member.get("global_name") or member.get("name") or ""
    ).lower()
    return (label, str(member.get("id") or ""))


def sort_members_deterministic(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(members, key=member_sort_key)


def filter_members(
    members: list[dict[str, Any]],
    *,
    q: str | None = None,
    exclude_bots: bool = True,
    only_member_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    filtered = members
    if exclude_bots:
        filtered = [member for member in filtered if not member.get("bot")]
    if only_member_ids is not None:
        filtered = [
            member for member in filtered if str(member.get("id") or "") in only_member_ids
        ]
    query = (q or "").strip().lower()
    if query:
        filtered = [
            member
            for member in filtered
            if query in str(member.get("name") or "").lower()
            or query in str(member.get("display_name") or "").lower()
            or query in str(member.get("global_name") or "").lower()
            or query in str(member.get("id") or "")
        ]
    return filtered


def paginate_members(
    members: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total = len(members)
    total_pages = max(1, math.ceil(total / limit)) if limit > 0 else 1
    page = min(max(1, (offset // limit) + 1), total_pages)
    safe_offset = (page - 1) * limit
    page_members = members[safe_offset : safe_offset + limit]
    pagination = {
        "offset": safe_offset,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "has_previous": page > 1,
        "has_next": page < total_pages,
    }
    return page_members, pagination


def merge_include_members(
    page_members: list[dict[str, Any]],
    all_members: list[dict[str, Any]],
    include_ids: list[str],
) -> list[dict[str, Any]]:
    if not include_ids:
        return page_members
    by_id = {str(member.get("id") or ""): member for member in all_members}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for member_id in include_ids:
        member = by_id.get(member_id)
        if member is None or member_id in seen:
            continue
        seen.add(member_id)
        merged.append(member)
    for member in page_members:
        member_id = str(member.get("id") or "")
        if not member_id or member_id in seen:
            continue
        seen.add(member_id)
        merged.append(member)
    return merged


def parse_include_member_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        member_id = part.strip()
        if not member_id.isdigit() or member_id in seen:
            continue
        seen.add(member_id)
        ids.append(member_id)
        if len(ids) >= 100:
            break
    return ids
