"""Server event log configuration and event feed."""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.db.session import get_database_session
from app.models.runtime_events import ServerEventLogEntry
from app.services.audit_detail import serialize_event_detail, serialize_event_summary
from app.services.campaign_store import get_redis, now_iso

router = APIRouter(
    tags=["Server Logs"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"


def logging_config_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:logging"


def event_log_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:eventlog"


class LoggingGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(__import__("uuid").uuid4()))
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    enabled: bool = True
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    event_keys: list[str] = Field(default_factory=list, max_length=32)


class LoggingConfig(BaseModel):
    enabled: bool = True
    log_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    member_events: bool = True
    message_events: bool = True
    role_events: bool = True
    channel_events: bool = True
    member_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    message_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    role_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    channel_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    groups: list[LoggingGroup] = Field(default_factory=list, max_length=20)


@router.get("/guilds/{guild_id}/logging")
async def get_logging_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(logging_config_key(guild_id))
    finally:
        await redis_client.aclose()

    defaults = LoggingConfig().model_dump()

    if not raw:
        return defaults

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return defaults

    if not isinstance(stored, dict):
        return defaults

    return {**defaults, **{k: v for k, v in stored.items() if k in defaults}}


@router.put("/guilds/{guild_id}/logging")
async def update_logging_config(
    guild_id: str,
    config: LoggingConfig,
) -> dict[str, Any]:
    payload = config.model_dump()
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await redis_client.set(logging_config_key(guild_id), json.dumps(payload))
    finally:
        await redis_client.aclose()

    return payload


@router.get("/guilds/{guild_id}/event-logs")
async def get_event_logs(
    guild_id: str,
    category: Optional[str] = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_database_session),
) -> list[dict[str, Any]]:
    query = (
        select(ServerEventLogEntry)
        .where(ServerEventLogEntry.guild_id == guild_id)
        .order_by(ServerEventLogEntry.created_at.desc())
        .limit(limit)
    )
    if category:
        query = query.where(ServerEventLogEntry.category == category)
    rows = (await session.scalars(query)).all()
    return [serialize_event_summary(row) for row in rows]


@router.get("/guilds/{guild_id}/event-logs/{event_id}")
async def get_event_log_detail(
    guild_id: str,
    event_id: UUID,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ServerEventLogEntry).where(
                ServerEventLogEntry.id == event_id,
                ServerEventLogEntry.guild_id == guild_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit event not found.")
    return serialize_event_detail(row)
