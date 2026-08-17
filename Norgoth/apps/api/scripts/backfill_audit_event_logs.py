"""One-shot copy of Redis eventlog/modlog rings into Postgres as legacy rows.

Does not invent field-level diffs. Existing ``source_event_id`` rows are skipped.

Usage:
    python -m scripts.backfill_audit_event_logs
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.runtime_events import ModerationLogEntry, ServerEventLogEntry
from app.services.audit_detail import EVENT_LOG_CAP, MODERATION_LOG_CAP, is_snowflake
from app.services.campaign_store import get_redis

logger = logging.getLogger("norgoth.backfill.audit_logs")

EVENT_KEY = "norgoth:guild:{guild_id}:eventlog"
MOD_KEY = "norgoth:guild:{guild_id}:modlog"


def _parse_created_at(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def _guild_ids(redis) -> set[str]:
    guilds: set[str] = set()
    cursor = 0
    while True:
        cursor, batch = await redis.scan(cursor, match="norgoth:guild:*:eventlog", count=200)
        for key in batch:
            parts = str(key).split(":")
            if len(parts) >= 3:
                guilds.add(parts[2])
        if cursor == 0:
            break
    cursor = 0
    while True:
        cursor, batch = await redis.scan(cursor, match="norgoth:guild:*:modlog", count=200)
        for key in batch:
            parts = str(key).split(":")
            if len(parts) >= 3:
                guilds.add(parts[2])
        if cursor == 0:
            break
    return {gid for gid in guilds if is_snowflake(gid)}


async def backfill() -> None:
    redis = await get_redis()
    factory = get_session_factory()
    events = 0
    mods = 0
    skipped = 0
    try:
        guild_ids = await _guild_ids(redis)
        for guild_id in sorted(guild_ids):
            raw_events = await redis.lrange(EVENT_KEY.format(guild_id=guild_id), 0, EVENT_LOG_CAP - 1)
            raw_mods = await redis.lrange(MOD_KEY.format(guild_id=guild_id), 0, MODERATION_LOG_CAP - 1)
            async with factory() as session:
                for raw in reversed(raw_events):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(parsed, dict):
                        continue
                    source_id = str(parsed.get("id") or "")[:36] or None
                    if source_id:
                        existing = (
                            await session.execute(
                                select(ServerEventLogEntry.id).where(
                                    ServerEventLogEntry.guild_id == guild_id,
                                    ServerEventLogEntry.source_event_id == source_id,
                                )
                            )
                        ).scalar_one_or_none()
                        if existing is not None:
                            skipped += 1
                            continue
                    created_at = _parse_created_at(parsed.get("created_at"))
                    row_id = None
                    if source_id:
                        try:
                            row_id = UUID(source_id)
                        except ValueError:
                            row_id = None
                    entry = ServerEventLogEntry(
                        guild_id=guild_id,
                        event_type=str(parsed.get("event_type") or "unknown")[:64],
                        category=str(parsed.get("category") or "server")[:32],
                        action=str(parsed.get("action") or "")[:128] or None,
                        actor_id=parsed.get("actor_id") if is_snowflake(str(parsed.get("actor_id") or "")) else None,
                        actor_name=str(parsed.get("actor_name") or "")[:128] or None,
                        source_event_id=source_id,
                        has_detail=False,
                        payload={
                            "description": parsed.get("description") or "",
                            "fields": parsed.get("fields") if isinstance(parsed.get("fields"), dict) else {},
                            "detail": None,
                            "schema_version": 0,
                        },
                    )
                    if row_id is not None:
                        entry.id = row_id
                    if created_at is not None:
                        entry.created_at = created_at
                    session.add(entry)
                    events += 1

                for raw in reversed(raw_mods):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(parsed, dict):
                        continue
                    details = {
                        "moderator_name": parsed.get("moderator_name"),
                        "target": parsed.get("target"),
                        "detail": parsed.get("detail"),
                    }
                    created_at = _parse_created_at(parsed.get("created_at"))
                    entry = ModerationLogEntry(
                        guild_id=guild_id,
                        action=str(parsed.get("action") or "unknown")[:32],
                        target_id=parsed.get("target_id") if is_snowflake(str(parsed.get("target_id") or "")) else None,
                        moderator_id=parsed.get("moderator_id") if is_snowflake(str(parsed.get("moderator_id") or "")) else None,
                        reason=str(parsed.get("reason") or "")[:512] or None,
                        details=details,
                    )
                    if created_at is not None:
                        entry.created_at = created_at
                    session.add(entry)
                    mods += 1
                await session.commit()
    finally:
        await redis.aclose()
    logger.info("Backfilled audit logs events=%s moderation=%s skipped=%s", events, mods, skipped)
    print(f"events={events} moderation={mods} skipped={skipped}")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(backfill())


if __name__ == "__main__":
    main()
