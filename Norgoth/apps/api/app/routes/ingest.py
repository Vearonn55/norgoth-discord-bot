"""Internal bot->API ingest endpoints for durable runtime events.

The bot stays DB-free and POSTs discrete events here (guarded by the shared
``X-Norgoth-Bot-Token``); the API persists them to Postgres (source of truth).
Hot per-message counters (XP, analytics, invites) stay Redis-first in the bot
and are rolled up here periodically.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_database_session
from app.models.runtime_events import (
    AnalyticsDaily,
    HoneypotTrigger,
    InviteCounter,
    MemberXp,
    ModerationLogEntry,
    RaidIncident,
    ServerEventLogEntry,
    Ticket,
)

SNOWFLAKE = r"^[0-9]{5,25}$"


async def require_bot_token(
    x_norgoth_bot_token: str | None = Header(default=None),
) -> None:
    """Guard internal endpoints: the bot and API share ``DISCORD_BOT_TOKEN``."""

    expected = get_settings().discord_bot_token
    if not expected or x_norgoth_bot_token != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token.")


router = APIRouter(
    prefix="/internal/ingest",
    tags=["Internal Ingest"],
    dependencies=[Depends(require_bot_token)],
)


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
    action: str
    target_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    moderator_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    reason: Optional[str] = None
    details: Optional[dict[str, Any]] = None


@router.post("/{guild_id}/moderation-log")
async def ingest_moderation_log(
    body: ModerationLogBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    entry = ModerationLogEntry(
        guild_id=guild_id,
        action=body.action,
        target_id=body.target_id,
        moderator_id=body.moderator_id,
        reason=body.reason,
        details=body.details,
    )
    session.add(entry)
    await session.commit()
    return {"id": str(entry.id)}


class ServerEventBody(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/{guild_id}/server-event")
async def ingest_server_event(
    body: ServerEventBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    entry = ServerEventLogEntry(
        guild_id=guild_id,
        event_type=body.event_type,
        payload=body.payload,
    )
    session.add(entry)
    await session.commit()
    return {"id": str(entry.id)}


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
        # award before the text ZSET was seeded from legacy totals).
        if text_xp <= 0 and row.text_xp > 0:
            text_xp = row.text_xp
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
