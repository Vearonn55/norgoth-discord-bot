"""Internal bot->API ingest endpoints for durable runtime events.

The bot stays DB-free and POSTs discrete events here (guarded by the shared
``X-Norgoth-Bot-Token``); the API persists them to Postgres (source of truth).
Hot per-message counters (XP, analytics, invites) stay Redis-first in the bot
and are rolled up here periodically.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import get_database_session
from app.security.internal_auth import require_internal_token
from app.models.runtime_events import (
    AnalyticsDaily,
    HoneypotTrigger,
    InviteCounter,
    InviteJoinEvent,
    InviteLifecycle,
    MemberXp,
    ModerationLogEntry,
    RaidIncident,
    ServerEventLogEntry,
    Ticket,
)
from app.repositories.discord_guild_repository import DiscordGuildRepository
from app.repositories.guild_active_ban_repository import GuildActiveBanRepository
from app.services.audit_detail import (
    EVENT_LOG_CAP,
    MODERATION_LOG_CAP,
    is_snowflake,
    prepare_event_payload,
)
from app.services.guild_ban_service import GuildBanService

SNOWFLAKE = r"^[0-9]{5,25}$"


def _guild_ban_service(session: AsyncSession) -> GuildBanService:
    return GuildBanService(
        guild_repository=DiscordGuildRepository(session),
        ban_repository=GuildActiveBanRepository(session),
    )


async def _sync_guild_ban_from_server_event(
    session: AsyncSession,
    *,
    guild_id: str,
    body: "ServerEventBody",
) -> None:
    if body.event_type not in {"member_ban", "member_unban"}:
        return

    payload = body.payload or {}
    target_id = payload.get("target_discord_user_id")
    if not isinstance(target_id, str) or not is_snowflake(target_id):
        return

    username = payload.get("username")
    display_name = payload.get("display_name")
    username_snapshot = username if isinstance(username, str) else None
    display_name_snapshot = display_name if isinstance(display_name, str) else None
    banned_at = body.created_at

    service = _guild_ban_service(session)
    if body.event_type == "member_ban":
        await service.upsert_active_ban(
            discord_guild_id=guild_id,
            discord_user_id=target_id,
            username_snapshot=username_snapshot,
            display_name_snapshot=display_name_snapshot,
            source="gateway_ban",
            banned_at=banned_at,
        )
    else:
        await service.deactivate_ban(
            discord_guild_id=guild_id,
            discord_user_id=target_id,
            source="gateway_unban",
            unbanned_at=banned_at,
        )


class GuildBanIngestBody(BaseModel):
    discord_user_id: str = Field(pattern=SNOWFLAKE)
    is_active: bool
    username: Optional[str] = Field(default=None, max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=200)
    source: str = Field(default="slash_ban", max_length=32)
    created_at: Optional[datetime] = None


router = APIRouter(
    prefix="/internal/ingest",
    tags=["Internal Ingest"],
    dependencies=[Depends(require_internal_token)],
)


@router.post("/{guild_id}/guild-ban")
async def ingest_guild_ban(
    body: GuildBanIngestBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    service = _guild_ban_service(session)
    if body.is_active:
        row = await service.upsert_active_ban(
            discord_guild_id=guild_id,
            discord_user_id=body.discord_user_id,
            username_snapshot=body.username,
            display_name_snapshot=body.display_name,
            source=body.source,
            banned_at=body.created_at,
        )
    else:
        row = await service.deactivate_ban(
            discord_guild_id=guild_id,
            discord_user_id=body.discord_user_id,
            source=body.source,
            unbanned_at=body.created_at,
        )
    await session.commit()
    return {"id": str(row.id) if row is not None else None, "synced": row is not None}


class RaidIncidentBody(BaseModel):
    joins_count: int = 0
    join_sample: list[Any] = Field(default_factory=list)
    status: str = "active"
    actions: list[Any] = Field(default_factory=list)


@router.post("/{guild_id}/raid-incident")
async def ingest_raid_incident(
    body: RaidIncidentBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    incident = RaidIncident(
        guild_id=guild_id,
        joins_count=body.joins_count,
        join_sample=body.join_sample,
        status=body.status,
        actions=body.actions,
    )
    session.add(incident)
    await session.commit()
    return {"id": str(incident.id)}


class HoneypotTriggerBody(BaseModel):
    user_id: str = Field(pattern=SNOWFLAKE)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    punishment: str = "log_only"
    details: Optional[dict[str, Any]] = None


@router.post("/{guild_id}/honeypot-trigger")
async def ingest_honeypot_trigger(
    body: HoneypotTriggerBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    trigger = HoneypotTrigger(
        guild_id=guild_id,
        user_id=body.user_id,
        channel_id=body.channel_id,
        punishment=body.punishment,
        details=body.details,
    )
    session.add(trigger)
    await session.commit()
    return {"id": str(trigger.id)}


class ModerationLogBody(BaseModel):
    action: str = Field(max_length=80)
    target_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    moderator_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    reason: Optional[str] = Field(default=None, max_length=512)
    details: Optional[dict[str, Any]] = None
    moderator_name: Optional[str] = Field(default=None, max_length=128)
    target: Optional[str] = Field(default=None, max_length=256)
    detail: Optional[str] = Field(default=None, max_length=512)
    created_at: Optional[datetime] = None


async def _prune_oldest(
    session: AsyncSession,
    model: type[ServerEventLogEntry] | type[ModerationLogEntry],
    guild_id: str,
    cap: int,
) -> None:
    count = await session.scalar(
        select(func.count()).select_from(model).where(model.guild_id == guild_id)
    )
    if not count or int(count) <= cap:
        return
    excess = int(count) - cap
    oldest_ids = (
        await session.scalars(
            select(model.id)
            .where(model.guild_id == guild_id)
            .order_by(model.created_at.asc())
            .limit(excess)
        )
    ).all()
    if oldest_ids:
        await session.execute(delete(model).where(model.id.in_(list(oldest_ids))))


@router.post("/{guild_id}/moderation-log")
async def ingest_moderation_log(
    body: ModerationLogBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    details = dict(body.details or {})
    if body.moderator_name:
        details["moderator_name"] = body.moderator_name
    if body.target:
        details["target"] = body.target
    if body.detail:
        details["detail"] = body.detail
    entry = ModerationLogEntry(
        guild_id=guild_id,
        action=(body.action or "")[:32],
        target_id=body.target_id if is_snowflake(body.target_id) else None,
        moderator_id=body.moderator_id if is_snowflake(body.moderator_id) else None,
        reason=body.reason,
        details=details or None,
    )
    if body.created_at is not None:
        entry.created_at = body.created_at
    session.add(entry)
    await session.flush()
    await _prune_oldest(session, ModerationLogEntry, guild_id, MODERATION_LOG_CAP)
    await session.commit()
    return {"id": str(entry.id)}


class ServerEventBody(BaseModel):
    event_type: str = Field(max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[str] = Field(default=None, max_length=36)
    category: Optional[str] = Field(default=None, max_length=32)
    action: Optional[str] = Field(default=None, max_length=128)
    actor_id: Optional[str] = Field(default=None, max_length=32)
    actor_name: Optional[str] = Field(default=None, max_length=128)
    created_at: Optional[datetime] = None
    discord_channel_id: Optional[str] = Field(default=None, max_length=32)
    discord_message_id: Optional[str] = Field(default=None, max_length=32)


class ServerEventPatchBody(BaseModel):
    actor_id: Optional[str] = Field(default=None, max_length=32)
    actor_name: Optional[str] = Field(default=None, max_length=128)
    actor_field: Optional[str] = Field(default=None, max_length=512)
    discord_channel_id: Optional[str] = Field(default=None, max_length=32)
    discord_message_id: Optional[str] = Field(default=None, max_length=32)
    detail_actor: Optional[dict[str, Any]] = None


@router.post("/{guild_id}/server-event")
async def ingest_server_event(
    body: ServerEventBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    source_id = body.source_event_id.strip() if body.source_event_id else None
    if source_id:
        existing = (
            await session.execute(
                select(ServerEventLogEntry).where(
                    ServerEventLogEntry.guild_id == guild_id,
                    ServerEventLogEntry.source_event_id == source_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"id": str(existing.id), "duplicate": True}

    payload, has_detail = prepare_event_payload(body.payload)
    actor_id = body.actor_id if is_snowflake(body.actor_id) else None
    entry = ServerEventLogEntry(
        guild_id=guild_id,
        event_type=body.event_type[:64],
        category=(body.category or None),
        action=(body.action or None),
        actor_id=actor_id,
        actor_name=(body.actor_name[:128] if body.actor_name else None),
        source_event_id=source_id,
        has_detail=has_detail,
        payload=payload,
        discord_channel_id=(
            body.discord_channel_id if is_snowflake(body.discord_channel_id) else None
        ),
        discord_message_id=(
            body.discord_message_id if is_snowflake(body.discord_message_id) else None
        ),
    )
    if body.created_at is not None:
        entry.created_at = body.created_at
    session.add(entry)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        if not source_id:
            raise
        existing = (
            await session.execute(
                select(ServerEventLogEntry).where(
                    ServerEventLogEntry.guild_id == guild_id,
                    ServerEventLogEntry.source_event_id == source_id,
                )
            )
        ).scalar_one_or_none()
        return {
            "id": str(existing.id) if existing is not None else "",
            "duplicate": True,
        }
    await _prune_oldest(session, ServerEventLogEntry, guild_id, EVENT_LOG_CAP)
    await _sync_guild_ban_from_server_event(session, guild_id=guild_id, body=body)
    await session.commit()
    return {"id": str(entry.id)}


@router.patch("/{guild_id}/server-event/{source_event_id}")
async def patch_server_event(
    body: ServerEventPatchBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    source_event_id: str = Path(min_length=1, max_length=36),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    existing = (
        await session.execute(
            select(ServerEventLogEntry).where(
                ServerEventLogEntry.guild_id == guild_id,
                ServerEventLogEntry.source_event_id == source_event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Server event not found.")

    if body.actor_id is not None:
        existing.actor_id = body.actor_id if is_snowflake(body.actor_id) else None
    if body.actor_name is not None:
        existing.actor_name = body.actor_name[:128]
    if body.discord_channel_id is not None:
        existing.discord_channel_id = (
            body.discord_channel_id if is_snowflake(body.discord_channel_id) else None
        )
    if body.discord_message_id is not None:
        existing.discord_message_id = (
            body.discord_message_id if is_snowflake(body.discord_message_id) else None
        )

    payload = dict(existing.payload or {})
    mutated = False
    if body.actor_field is not None:
        fields = dict(payload.get("fields") or {})
        fields["Actor"] = body.actor_field
        payload["fields"] = fields
        mutated = True
    if body.detail_actor is not None:
        detail = dict(payload.get("detail") or {})
        detail["actor"] = body.detail_actor
        payload["detail"] = detail
        mutated = True
    if mutated:
        existing.payload = payload
        flag_modified(existing, "payload")

    await session.commit()
    return {"id": str(existing.id), "updated": True}


class InviteEventBody(BaseModel):
    inviter_id: str = Field(pattern=SNOWFLAKE)
    name: Optional[str] = None
    joins_delta: int = 0
    leaves_delta: int = 0
    rejoins_delta: int = 0


@router.post("/{guild_id}/invite-event")
async def ingest_invite_event(
    body: InviteEventBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    counter = (
        await session.execute(
            select(InviteCounter)
            .where(
                InviteCounter.guild_id == guild_id,
                InviteCounter.inviter_id == body.inviter_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if counter is None:
        counter = InviteCounter(guild_id=guild_id, inviter_id=body.inviter_id)
        session.add(counter)
    if body.name is not None:
        counter.name = body.name
    counter.joins += body.joins_delta
    counter.leaves += body.leaves_delta
    counter.rejoins += body.rejoins_delta
    await session.commit()
    return {
        "inviter_id": body.inviter_id,
        "joins": counter.joins,
        "leaves": counter.leaves,
        "rejoins": counter.rejoins,
    }


class InviteJoinBody(BaseModel):
    member_id: str = Field(pattern=SNOWFLAKE)
    inviter_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    code: Optional[str] = Field(default=None, max_length=64)
    attribution: str = Field(default="unknown", max_length=32)
    rejoin: bool = False
    joined_at: Optional[datetime] = None
    inviter_name: Optional[str] = Field(default=None, max_length=100)


@router.post("/{guild_id}/invite-join")
async def ingest_invite_join(
    body: InviteJoinBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    event = InviteJoinEvent(
        guild_id=guild_id,
        member_id=body.member_id,
        inviter_id=body.inviter_id,
        code=body.code,
        attribution=body.attribution,
        rejoin=body.rejoin,
        joined_at=body.joined_at or datetime.now(timezone.utc),
    )
    session.add(event)
    if body.inviter_id and body.attribution in {
        "attributed",
        "consumed_one_use",
        "deleted",
    }:
        counter = (
            await session.execute(
                select(InviteCounter)
                .where(
                    InviteCounter.guild_id == guild_id,
                    InviteCounter.inviter_id == body.inviter_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if counter is None:
            counter = InviteCounter(
                guild_id=guild_id, inviter_id=body.inviter_id
            )
            session.add(counter)
        if body.inviter_name is not None:
            counter.name = body.inviter_name
        counter.joins += 1
        if body.rejoin:
            counter.rejoins += 1
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(
                select(InviteJoinEvent).where(
                    InviteJoinEvent.guild_id == guild_id,
                    InviteJoinEvent.member_id == body.member_id,
                    InviteJoinEvent.joined_at == (body.joined_at or event.joined_at),
                )
            )
        ).scalar_one_or_none()
        return {
            "id": str(existing.id) if existing is not None else "",
            "attribution": existing.attribution if existing is not None else body.attribution,
            "duplicate": True,
        }
    return {"id": str(event.id), "attribution": event.attribution}


def _invite_kind(*, code: str, max_uses: int | None, invite_kind: str | None) -> str:
    if code == "vanity" or invite_kind == "vanity":
        return "vanity"
    if invite_kind in {"one_use", "standard", "vanity"}:
        if max_uses == 1:
            return "one_use"
        return invite_kind
    if max_uses == 1:
        return "one_use"
    return "standard"


class InviteLifecycleBody(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    inviter_id: Optional[str] = Field(default=None, max_length=32)
    inviter_name_snapshot: Optional[str] = Field(default=None, max_length=128)
    channel_id: Optional[str] = Field(default=None, max_length=32)
    uses: int = Field(default=0, ge=0)
    max_uses: Optional[int] = Field(default=None, ge=0)
    max_age: Optional[int] = Field(default=None, ge=0)
    temporary: bool = False
    created_at_discord: Optional[datetime] = None
    status: str = Field(default="active", max_length=16)
    invite_kind: Optional[str] = Field(default=None, max_length=16)
    disappeared_at: Optional[datetime] = None


class InviteLifecycleSnapshotBody(BaseModel):
    invites: list[InviteLifecycleBody] = Field(default_factory=list, max_length=200)


async def _upsert_invite_lifecycle(
    session: AsyncSession,
    guild_id: str,
    body: InviteLifecycleBody,
    *,
    now: datetime,
) -> InviteLifecycle:
    row = (
        await session.execute(
            select(InviteLifecycle)
            .where(
                InviteLifecycle.guild_id == guild_id,
                InviteLifecycle.code == body.code,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    kind = _invite_kind(
        code=body.code,
        max_uses=body.max_uses,
        invite_kind=body.invite_kind,
    )
    inviter_id = body.inviter_id if is_snowflake(body.inviter_id) else None
    channel_id = body.channel_id if is_snowflake(body.channel_id) else None
    if row is None:
        row = InviteLifecycle(
            guild_id=guild_id,
            code=body.code[:64],
            inviter_id=inviter_id,
            inviter_name_snapshot=body.inviter_name_snapshot,
            channel_id=channel_id,
            uses=body.uses,
            max_uses=body.max_uses,
            max_age=body.max_age,
            temporary=body.temporary,
            created_at_discord=body.created_at_discord,
            last_seen_at=now,
            disappeared_at=body.disappeared_at,
            status=body.status[:16],
            invite_kind=kind,
        )
        session.add(row)
        return row

    if inviter_id and not row.inviter_id:
        row.inviter_id = inviter_id
    if body.inviter_name_snapshot and not row.inviter_name_snapshot:
        row.inviter_name_snapshot = body.inviter_name_snapshot
    if channel_id:
        row.channel_id = channel_id
    row.uses = body.uses
    if body.max_uses is not None:
        row.max_uses = body.max_uses
    if body.max_age is not None:
        row.max_age = body.max_age
    row.temporary = body.temporary
    if body.created_at_discord is not None:
        row.created_at_discord = body.created_at_discord
    row.last_seen_at = now
    row.status = body.status[:16]
    row.invite_kind = kind
    if body.disappeared_at is not None:
        row.disappeared_at = body.disappeared_at
    elif body.status == "active":
        row.disappeared_at = None
    return row


async def _prune_stale_invite_lifecycle(
    session: AsyncSession,
    guild_id: str,
    *,
    now: datetime,
) -> None:
    cutoff = now - timedelta(days=7)
    await session.execute(
        delete(InviteLifecycle).where(
            InviteLifecycle.guild_id == guild_id,
            InviteLifecycle.disappeared_at.is_not(None),
            InviteLifecycle.disappeared_at < cutoff,
        )
    )


@router.post("/{guild_id}/invite-lifecycle")
async def ingest_invite_lifecycle(
    body: InviteLifecycleBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    row = await _upsert_invite_lifecycle(session, guild_id, body, now=now)
    await _prune_stale_invite_lifecycle(session, guild_id, now=now)
    await session.commit()
    return {
        "id": str(row.id),
        "code": row.code,
        "status": row.status,
        "invite_kind": row.invite_kind,
        "inviter_id": row.inviter_id,
    }


@router.post("/{guild_id}/invite-lifecycle/snapshot")
async def ingest_invite_lifecycle_snapshot(
    body: InviteLifecycleSnapshotBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    upserted = 0
    for item in body.invites:
        await _upsert_invite_lifecycle(session, guild_id, item, now=now)
        upserted += 1
    await _prune_stale_invite_lifecycle(session, guild_id, now=now)
    await session.commit()
    return {"upserted": upserted}


@router.get("/{guild_id}/invite-lifecycle/recent-vanished")
async def get_recent_vanished_invites(
    guild_id: str = Path(pattern=SNOWFLAKE),
    since_seconds: int = Query(default=600, ge=1, le=3600),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=since_seconds)
    rows = (
        await session.execute(
            select(InviteLifecycle).where(
                InviteLifecycle.guild_id == guild_id,
                InviteLifecycle.status.in_(("consumed", "deleted", "expired")),
                InviteLifecycle.disappeared_at.is_not(None),
                InviteLifecycle.disappeared_at >= cutoff,
            )
        )
    ).scalars().all()
    return {
        "invites": [
            {
                "code": row.code,
                "inviter_id": row.inviter_id,
                "inviter_name": row.inviter_name_snapshot,
                "channel_id": row.channel_id,
                "uses": row.uses,
                "max_uses": row.max_uses,
                "status": row.status,
                "invite_kind": row.invite_kind,
                "disappeared_at": (
                    row.disappeared_at.isoformat() if row.disappeared_at else None
                ),
            }
            for row in rows
        ]
    }


class XpClearBody(BaseModel):
    user_id: str = Field(pattern=SNOWFLAKE)


@router.post("/{guild_id}/xp-clear")
async def ingest_xp_clear(
    body: XpClearBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(MemberXp)
            .where(MemberXp.guild_id == guild_id, MemberXp.user_id == body.user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    deleted = False
    if row is not None:
        await session.delete(row)
        await session.commit()
        deleted = True
    else:
        await session.commit()
    return {"user_id": body.user_id, "deleted": deleted}


class XpRollupBody(BaseModel):
    user_id: str = Field(pattern=SNOWFLAKE)
    text_xp: int = Field(default=0, ge=0)
    voice_xp: int = Field(default=0, ge=0)
    # Legacy clients may still send a single total; prefer text_xp+voice_xp.
    xp: int | None = Field(default=None, ge=0)


@router.post("/{guild_id}/xp")
async def ingest_xp(
    body: XpRollupBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    text_xp = body.text_xp
    voice_xp = body.voice_xp
    if body.xp is not None and text_xp == 0 and voice_xp == 0:
        # Pre-split clients: attribute the total to text XP.
        text_xp = body.xp
    total = text_xp + voice_xp

    row = (
        await session.execute(
            select(MemberXp)
            .where(MemberXp.guild_id == guild_id, MemberXp.user_id == body.user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = MemberXp(
            guild_id=guild_id,
            user_id=body.user_id,
            xp=total,
            text_xp=text_xp,
            voice_xp=voice_xp,
        )
        session.add(row)
    else:
        # Merge-safe: never wipe accrued text_xp with an accidental 0 (e.g. voice
        # award before the text ZSET was seeded from legacy totals). Same for
        # voice_xp when a text-only ingest arrives with voice_xp=0.
        if text_xp <= 0 and row.text_xp > 0:
            text_xp = row.text_xp
        if voice_xp <= 0 and row.voice_xp > 0:
            voice_xp = row.voice_xp
        total = text_xp + voice_xp
        row.text_xp = text_xp
        row.voice_xp = voice_xp
        row.xp = total
    await session.commit()
    return {
        "user_id": body.user_id,
        "xp": row.xp,
        "text_xp": row.text_xp,
        "voice_xp": row.voice_xp,
    }


class AnalyticsDailyBody(BaseModel):
    day: date
    messages: int = 0
    unique_authors: int = 0
    joins: int = 0
    leaves: int = 0
    voice_uniques: int = 0


@router.post("/{guild_id}/analytics-daily")
async def ingest_analytics_daily(
    body: AnalyticsDailyBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(AnalyticsDaily)
            .where(AnalyticsDaily.guild_id == guild_id, AnalyticsDaily.day == body.day)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = AnalyticsDaily(guild_id=guild_id, day=body.day)
        session.add(row)
    row.messages = body.messages
    row.unique_authors = body.unique_authors
    row.joins = body.joins
    row.leaves = body.leaves
    row.voice_uniques = body.voice_uniques
    await session.commit()
    return {"guild_id": guild_id, "day": body.day.isoformat()}


class TicketUpsertBody(BaseModel):
    number: int
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    opener_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    subject: Optional[str] = None
    status: str = "open"
    closed_at: Optional[datetime] = None
    transcript: Optional[str] = None


@router.post("/{guild_id}/ticket")
async def ingest_ticket(
    body: TicketUpsertBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from app.models.runtime_events import TicketTranscript
    from sqlalchemy.orm import selectinload

    ticket = (
        await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.transcript))
            .where(Ticket.guild_id == guild_id, Ticket.number == body.number)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if ticket is None:
        ticket = Ticket(guild_id=guild_id, number=body.number)
        session.add(ticket)
    ticket.channel_id = body.channel_id
    ticket.opener_id = body.opener_id
    ticket.subject = body.subject
    ticket.status = body.status
    ticket.closed_at = body.closed_at

    if body.transcript is not None:
        await session.flush()
        if ticket.transcript is None:
            session.add(
                TicketTranscript(ticket_id=ticket.id, content=body.transcript)
            )
        else:
            ticket.transcript.content = body.transcript

    await session.commit()
    return {"id": str(ticket.id), "number": ticket.number}


class FeedMessageBody(BaseModel):
    channel_id: str = Field(pattern=SNOWFLAKE)
    message_id: str = Field(pattern=SNOWFLAKE)
    author_id: str = Field(pattern=SNOWFLAKE)
    created_at: datetime
    content_excerpt: Optional[str] = None
    attachment_count: int = 0
    primary_media_url: Optional[str] = Field(default=None, max_length=1024)
    author_display_name: Optional[str] = Field(default=None, max_length=128)
    author_avatar_url: Optional[str] = Field(default=None, max_length=1024)


class FeedVoteBody(BaseModel):
    message_id: str = Field(pattern=SNOWFLAKE)
    voter_id: str = Field(pattern=SNOWFLAKE)
    # None clears the vote; "up" / "down" sets it.
    vote: Optional[Literal["up", "down"]] = None
    # When true, message_id may be a feed slot id — resolve to source.
    from_feed_entry: bool = False


class FeedMessageEditBody(BaseModel):
    message_id: str = Field(pattern=SNOWFLAKE)
    content_excerpt: Optional[str] = None
    attachment_count: Optional[int] = None
    primary_media_url: Optional[str] = Field(default=None, max_length=1024)
    author_display_name: Optional[str] = Field(default=None, max_length=128)
    author_avatar_url: Optional[str] = Field(default=None, max_length=1024)


class FeedMessageDeleteBody(BaseModel):
    message_id: str = Field(pattern=SNOWFLAKE)


@router.post("/{guild_id}/feed-message")
async def ingest_feed_message(
    body: FeedMessageBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from app.services.feed_service import mark_windows_dirty, track_feed_message

    row = await track_feed_message(
        session,
        guild_id=guild_id,
        channel_id=body.channel_id,
        message_id=body.message_id,
        author_id=body.author_id,
        created_at=body.created_at,
        content_excerpt=body.content_excerpt,
        attachment_count=body.attachment_count,
        primary_media_url=body.primary_media_url,
        author_display_name=body.author_display_name,
        author_avatar_url=body.author_avatar_url,
    )
    await session.commit()
    await mark_windows_dirty(guild_id, row.created_at)
    return {"ok": True, "message_id": row.message_id, "status": row.status}


@router.post("/{guild_id}/feed-vote")
async def ingest_feed_vote(
    body: FeedVoteBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from datetime import timezone

    from app.services.feed_rebuild import resolve_source_message_id
    from app.services.feed_service import (
        apply_feed_vote,
        mark_windows_dirty,
        warm_author_net_cache,
        warm_message_rank_cache,
    )
    from app.models.feed_channels import FeedMessage
    from sqlalchemy import select

    source_id = body.message_id
    if body.from_feed_entry:
        source_id = await resolve_source_message_id(
            session, guild_id=guild_id, message_id=body.message_id
        )

    result = await apply_feed_vote(
        session,
        guild_id=guild_id,
        message_id=source_id,
        voter_id=body.voter_id,
        vote=body.vote,
    )
    await session.commit()

    if result.get("ok") and result.get("changed"):
        msg = (
            await session.execute(
                select(FeedMessage).where(
                    FeedMessage.guild_id == guild_id,
                    FeedMessage.message_id == source_id,
                )
            )
        ).scalar_one_or_none()
        if msg is not None:
            await warm_message_rank_cache(guild_id, msg)
            await mark_windows_dirty(guild_id, msg.created_at)
        if result.get("author_id") is not None:
            await warm_author_net_cache(
                guild_id, str(result["author_id"]), int(result.get("author_net") or 0)
            )

    result["source_message_id"] = source_id
    result["previous_vote"] = result.get("previous")
    return result


@router.post("/{guild_id}/feed-message-edited")
async def ingest_feed_message_edited(
    body: FeedMessageEditBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from app.services.feed_service import mark_windows_dirty, update_feed_message_excerpt

    row = await update_feed_message_excerpt(
        session,
        guild_id=guild_id,
        message_id=body.message_id,
        content_excerpt=body.content_excerpt,
        attachment_count=body.attachment_count,
        primary_media_url=body.primary_media_url,
        author_display_name=body.author_display_name,
        author_avatar_url=body.author_avatar_url,
    )
    await session.commit()
    if row is not None and row.status == "active":
        await mark_windows_dirty(guild_id, row.created_at)
    return {"ok": True, "updated": row is not None}


@router.post("/{guild_id}/feed-message-deleted")
async def ingest_feed_message_deleted(
    body: FeedMessageDeleteBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from datetime import timezone

    from app.services.feed_service import (
        mark_feed_message_deleted,
        mark_windows_dirty,
        remove_message_from_rank_cache,
        warm_author_net_cache,
    )
    from app.models.feed_channels import FeedAuthorStats
    from sqlalchemy import select

    row = await mark_feed_message_deleted(
        session, guild_id=guild_id, message_id=body.message_id
    )
    await session.commit()
    if row is not None:
        await remove_message_from_rank_cache(guild_id, body.message_id)
        await mark_windows_dirty(guild_id, row.created_at or datetime.now(timezone.utc))
        stats = (
            await session.execute(
                select(FeedAuthorStats).where(
                    FeedAuthorStats.guild_id == guild_id,
                    FeedAuthorStats.user_id == row.author_id,
                )
            )
        ).scalar_one_or_none()
        if stats is not None:
            await warm_author_net_cache(guild_id, row.author_id, int(stats.net_score))
    return {"ok": True, "deleted": row is not None}


@router.post("/{guild_id}/feed-process-dirty")
async def ingest_feed_process_dirty(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from app.services.feed_rebuild import process_dirty_feeds

    results = await process_dirty_feeds(session, guild_id)
    return {"guild_id": guild_id, "results": results}


@router.post("/{guild_id}/feed-repair")
async def ingest_feed_repair(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    from app.services.feed_repair import repair_feed_channels

    return await repair_feed_channels(session, guild_id=guild_id)


class FeedRefreshWindowBody(BaseModel):
    window: Literal["daily", "weekly", "monthly", "all_time"]


@router.post("/{guild_id}/feed-refresh-window")
async def ingest_feed_refresh_window(
    body: FeedRefreshWindowBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Rebuild a single due Top Trending window and advance its schedule."""

    from app.services.feature_config_store import save_config
    from app.services.feed_ranking import (
        load_merged_feed_config,
        schedule_window_after_failure,
        schedule_window_after_success,
        scheduler_countdown_fields,
    )
    from app.services.feed_rebuild import rebuild_feed_window

    config = await load_merged_feed_config(guild_id)
    result = await rebuild_feed_window(
        session,
        guild_id=guild_id,
        window=body.window,
        config=config,
    )
    if result.get("ok"):
        schedule_window_after_success(config, body.window)
        await save_config(
            guild_id, "feed_channels", config, enabled=bool(config.get("enabled"))
        )
    elif result.get("reason") not in {"locked", "window_not_configured"}:
        schedule_window_after_failure(config, body.window)
        await save_config(
            guild_id, "feed_channels", config, enabled=bool(config.get("enabled"))
        )
    return {
        "guild_id": guild_id,
        "window": body.window,
        "result": result,
        **scheduler_countdown_fields(config),
    }


# Backward-compatible alias for older bot builds.
@router.post("/{guild_id}/feed-reconcile")
async def ingest_feed_reconcile(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    return await ingest_feed_repair(guild_id=guild_id, session=session)


@router.get("/{guild_id}/verification-pending-count")
async def verification_pending_count(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Return open manual-review verification attempt count for Discord /verification pending."""

    from app.models.enums import VerificationStatus
    from app.repositories.verification_log_repository import (
        VerificationLogRepository,
    )

    guild = await DiscordGuildRepository(session).get_by_discord_guild_id(guild_id)
    if guild is None:
        return {"guild_id": guild_id, "count": 0}

    count = await VerificationLogRepository(session).count_by_guild(
        guild_id=guild.id,
        status=VerificationStatus.MANUAL_REVIEW,
    )
    return {"guild_id": guild_id, "count": int(count)}

