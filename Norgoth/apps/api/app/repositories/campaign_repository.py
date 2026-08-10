"""Postgres persistence for campaigns (durable source of truth).

Redis remains the hot cache and owns the execution queue / schedule zset.
Campaign definition and runtime counters live in ``campaigns.raw_payload`` with
thin column mirrors for querying.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_events import Campaign, CampaignActivity

# Keys mirrored on first-class columns; everything else stays in raw_payload.
_COLUMN_KEYS = frozenset(
    {
        "id",
        "guild_id",
        "name",
        "title",
        "status",
        "platform_messages",
        "audience",
        "created_by",
        "launch_at",
        "next_run_at",
        "created_at",
        "updated_at",
        "raw_payload",
    }
)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def campaign_dict_to_columns(campaign: dict[str, Any]) -> dict[str, Any]:
    """Split a Redis-shaped campaign dict into ORM column values + raw_payload."""

    name = str(campaign.get("title") or campaign.get("name") or "Untitled Campaign")[
        :200
    ]
    audience = campaign.get("audience")
    if not isinstance(audience, dict):
        audience = {}

    platform_messages = campaign.get("platform_messages")
    if not isinstance(platform_messages, dict):
        platform_messages = {}

    raw_payload = {
        key: value for key, value in campaign.items() if key not in _COLUMN_KEYS
    }
    if "title" in campaign:
        raw_payload.setdefault("title", campaign.get("title"))
    if "name" in campaign and campaign.get("name") != name:
        raw_payload.setdefault("name", campaign.get("name"))

    return {
        "id": UUID(str(campaign["id"])),
        "guild_id": str(campaign["guild_id"]),
        "name": name,
        "status": str(campaign.get("status") or "draft")[:32],
        "platform_messages": platform_messages,
        "audience": audience,
        "raw_payload": raw_payload,
        "created_by": (
            str(campaign["created_by"]) if campaign.get("created_by") else None
        ),
        "launch_at": _parse_datetime(campaign.get("launch_at")),
        "next_run_at": _parse_datetime(campaign.get("next_run_at")),
    }


def row_to_campaign_dict(row: Campaign) -> dict[str, Any]:
    """Rebuild the Redis-shaped campaign dict from a Postgres row."""

    payload: dict[str, Any] = {}
    if isinstance(row.raw_payload, dict):
        payload.update(row.raw_payload)

    payload["id"] = str(row.id)
    payload["guild_id"] = row.guild_id
    payload["name"] = row.name
    payload["title"] = payload.get("title") or row.name
    payload["status"] = row.status
    payload["platform_messages"] = row.platform_messages or {}
    payload["audience"] = row.audience or {}
    if row.created_by is not None:
        payload["created_by"] = row.created_by
    if row.launch_at is not None:
        payload["launch_at"] = row.launch_at.isoformat()
    if row.next_run_at is not None:
        payload["next_run_at"] = row.next_run_at.isoformat()
    if row.created_at is not None:
        payload["created_at"] = row.created_at.isoformat()
    if row.updated_at is not None:
        payload["updated_at"] = row.updated_at.isoformat()

    return payload


class CampaignRepository:
    """CRUD helpers for the campaigns table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, campaign: dict[str, Any]) -> Campaign:
        columns = campaign_dict_to_columns(campaign)
        row = await self._session.get(Campaign, columns["id"])
        if row is None:
            row = Campaign(**columns)
            self._session.add(row)
        else:
            for key, value in columns.items():
                if key == "id":
                    continue
                setattr(row, key, value)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def get(self, campaign_id: str) -> Campaign | None:
        try:
            uid = UUID(str(campaign_id))
        except ValueError:
            return None
        return await self._session.get(Campaign, uid)

    async def list_all(self) -> list[Campaign]:
        result = await self._session.execute(select(Campaign))
        return list(result.scalars().all())

    async def delete(self, campaign_id: str) -> None:
        try:
            uid = UUID(str(campaign_id))
        except ValueError:
            return
        await self._session.execute(delete(Campaign).where(Campaign.id == uid))
        await self._session.commit()

    async def add_activity(
        self,
        campaign_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            uid = UUID(str(campaign_id))
        except ValueError:
            return
        self._session.add(
            CampaignActivity(campaign_id=uid, kind=kind[:64], payload=payload)
        )
        await self._session.commit()
