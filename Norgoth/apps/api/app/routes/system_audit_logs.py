"""Paginated read API for durable system_audit_log entries."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.db.session import get_database_session
from app.models.system_audit_log import SystemAuditLog

router = APIRouter(
    tags=["System Audit"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"


class SystemAuditEntry(BaseModel):
    id: int
    guild_id: Optional[str] = None
    entity_type: str
    entity_id: Optional[str] = None
    action: str
    actor_id: Optional[UUID] = None
    changes: Any = None
    created_at: str


class SystemAuditPage(BaseModel):
    items: list[SystemAuditEntry]
    total: int
    limit: int
    offset: int


@router.get(
    "/guilds/{guild_id}/system-audit-logs",
    response_model=SystemAuditPage,
)
async def list_system_audit_logs(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    entity_type: Optional[str] = Query(default=None, max_length=64),
    action: Optional[str] = Query(default=None, max_length=32),
    session: AsyncSession = Depends(get_database_session),
) -> SystemAuditPage:
    """Return durable app configuration audit rows for a guild."""

    filters = [SystemAuditLog.guild_id == guild_id]
    if entity_type:
        filters.append(SystemAuditLog.entity_type == entity_type)
    if action:
        filters.append(SystemAuditLog.action == action)

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(SystemAuditLog).where(*filters)
            )
        ).scalar_one()
    )

    rows = (
        await session.execute(
            select(SystemAuditLog)
            .where(*filters)
            .order_by(SystemAuditLog.created_at.desc(), SystemAuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    items = [
        SystemAuditEntry(
            id=row.id,
            guild_id=row.guild_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            actor_id=row.actor_id,
            changes=row.changes,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]

    return SystemAuditPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
