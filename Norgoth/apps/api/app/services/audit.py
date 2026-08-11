"""Audit-hook helper for recording durable configuration and state changes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_audit_log import SystemAuditLog


async def record_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    action: str,
    guild_id: str | None = None,
    entity_id: str | None = None,
    actor_id: UUID | None = None,
    changes: dict[str, Any] | list[Any] | None = None,
) -> SystemAuditLog:
    """Stage an audit entry on the session (caller owns the commit boundary).

    Args:
        entity_type: The logical entity changed (for example ``"automod_config"``).
        action: A short verb such as ``"create"``, ``"update"``, ``"delete"``.
        guild_id: The guild snowflake the change belongs to, when applicable.
        entity_id: An identifier of the changed row (stringified UUID or key).
        actor_id: The ``discord_users.id`` of the actor, when known.
        changes: An optional JSON-serialisable diff or payload snapshot.
    """

    entry = SystemAuditLog(
        entity_type=entity_type,
        action=action,
        guild_id=guild_id,
        entity_id=entity_id,
        actor_id=actor_id,
        changes=changes,
    )
    session.add(entry)
    return entry
