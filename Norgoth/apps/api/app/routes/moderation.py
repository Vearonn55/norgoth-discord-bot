"""Moderation audit log, written by the bot and stored in Postgres."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.db.session import get_database_session
from app.models.runtime_events import ModerationLogEntry

router = APIRouter(
    tags=["Moderation"],
    dependencies=[Depends(guild_manager_dependency())],
)


def serialize_moderation_entry(row: ModerationLogEntry) -> dict[str, Any]:
    details = row.details if isinstance(row.details, dict) else {}
    created = row.created_at.isoformat() if row.created_at else ""
    return {
        "id": str(row.id),
        "action": row.action,
        "moderator_id": row.moderator_id,
        "moderator_name": details.get("moderator_name") or row.moderator_id or "—",
        "target": details.get("target") or row.target_id or "—",
        "reason": row.reason or "",
        "detail": details.get("detail"),
        "created_at": created,
    }


@router.get("/guilds/{guild_id}/moderation-logs")
async def get_moderation_logs(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_database_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(ModerationLogEntry)
            .where(ModerationLogEntry.guild_id == guild_id)
            .order_by(ModerationLogEntry.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [serialize_moderation_entry(row) for row in rows]
