"""Persist normalized events and fan out notification jobs to guild subscriptions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
)
from app.models.content_notifications import (
    ContentCreatorSource,
    GuildContentSubscription,
    NormalizedContentEventRow,
    NotificationJob,
)
from app.services.content_notifications.avatar import persistable_source_avatar

logger = logging.getLogger("norgoth.content.fanout")


@dataclass(slots=True)
class FanoutResult:
    """Result of persisting an event and creating delivery jobs.

    Callers must ``commit`` the session, then enqueue ``job_ids``. Enqueuing
    before commit races the worker (job row not visible yet → silent drop).
    """

    event: NormalizedContentEventRow | None
    job_ids: list[UUID] = field(default_factory=list)
    deduplicated: bool = False


async def persist_and_fanout(
    session: AsyncSession,
    event: NormalizedContentEvent,
    *,
    source: ContentCreatorSource | None = None,
) -> FanoutResult:
    """Idempotently store an event and create one job per matching guild subscription.

    Does **not** push to Redis — callers must enqueue ``job_ids`` after commit.
    """

    if source is None:
        source = await session.scalar(
            select(ContentCreatorSource).where(
                ContentCreatorSource.platform == event.platform.value,
                ContentCreatorSource.platform_creator_id == event.creator_platform_id,
            )
        )
    if source is None:
        logger.warning(
            "No content source for %s/%s",
            event.platform,
            event.creator_platform_id,
        )
        return FanoutResult(event=None)

    stmt = (
        insert(NormalizedContentEventRow)
        .values(
            platform=event.platform.value,
            event_type=event.event_type.value,
            source_id=source.id,
            external_content_id=event.external_content_id,
            creator_name=event.creator_name,
            creator_avatar=event.creator_avatar,
            title=event.title,
            description=event.description,
            content_url=event.content_url,
            playable_url=event.playable_url,
            thumbnail_url=event.thumbnail_url,
            published_at=event.published_at,
            is_live=event.is_live,
            game=event.game,
            category=event.category,
            viewer_count=event.viewer_count,
            raw_metadata=event.raw_metadata or {},
            received_at=datetime.now(timezone.utc),
            enriched_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(
            constraint="uq_normalized_content_events_dedupe",
        )
        .returning(NormalizedContentEventRow.id)
    )
    result = await session.execute(stmt)
    event_id = result.scalar_one_or_none()
    if event_id is None:
        # Duplicate — already processed.
        existing = await session.scalar(
            select(NormalizedContentEventRow).where(
                NormalizedContentEventRow.platform == event.platform.value,
                NormalizedContentEventRow.external_content_id
                == event.external_content_id,
                NormalizedContentEventRow.event_type == event.event_type.value,
            )
        )
        return FanoutResult(event=existing, deduplicated=True)

    row = await session.get(NormalizedContentEventRow, event_id)
    source.last_event_at = datetime.now(timezone.utc)
    event_avatar = persistable_source_avatar(source.platform, event.creator_avatar)
    if event_avatar:
        source.avatar_url = event_avatar
        source.avatar_checked_at = datetime.now(timezone.utc)

    subscriptions = (
        await session.scalars(
            select(GuildContentSubscription).where(
                GuildContentSubscription.source_id == source.id,
                GuildContentSubscription.enabled.is_(True),
            )
        )
    ).all()

    job_ids: list[UUID] = []
    for sub in subscriptions:
        event_types = sub.event_types or []
        if event_types and event.event_type.value not in event_types:
            continue
        job_stmt = (
            insert(NotificationJob)
            .values(
                event_id=event_id,
                subscription_id=sub.id,
                status="queued",
                attempt_count=0,
                next_attempt_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(
                constraint="uq_notification_jobs_event_subscription",
            )
            .returning(NotificationJob.id)
        )
        job_result = await session.execute(job_stmt)
        job_id = job_result.scalar_one_or_none()
        if job_id is not None:
            job_ids.append(job_id)
            sub.last_event_id = event_id
            sub.last_event_at = datetime.now(timezone.utc)
            if sub.status == "waiting_first_event":
                sub.status = "subscription_healthy"

    await session.flush()
    return FanoutResult(event=row, job_ids=job_ids)


def event_from_row(row: NormalizedContentEventRow) -> NormalizedContentEvent:
    from app.integrations.content_platforms.types import PlatformType

    return NormalizedContentEvent(
        platform=PlatformType(row.platform),
        event_type=ContentEventType(row.event_type),
        external_content_id=row.external_content_id,
        creator_platform_id="",  # filled by caller if needed
        creator_name=row.creator_name,
        creator_avatar=row.creator_avatar,
        title=row.title,
        description=row.description,
        content_url=row.content_url,
        playable_url=row.playable_url,
        thumbnail_url=row.thumbnail_url,
        published_at=row.published_at,
        is_live=row.is_live,
        game=row.game,
        category=row.category,
        viewer_count=row.viewer_count,
        raw_metadata=row.raw_metadata or {},
        source_id=row.source_id,
        event_id=row.id,
    )


async def ensure_source(
    session: AsyncSession,
    *,
    platform: str,
    platform_creator_id: str,
    username: str,
    display_name: str,
    profile_url: str,
    avatar_url: str | None = None,
    canonical_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    monitor_status: str = "active",
) -> ContentCreatorSource:
    existing = await session.scalar(
        select(ContentCreatorSource).where(
            ContentCreatorSource.platform == platform,
            ContentCreatorSource.platform_creator_id == platform_creator_id,
        )
    )
    normalized_avatar = persistable_source_avatar(platform, avatar_url)
    now = datetime.now(timezone.utc)
    if existing:
        existing.username = username or existing.username
        existing.display_name = display_name or existing.display_name
        existing.profile_url = profile_url or existing.profile_url
        existing.avatar_checked_at = now
        if normalized_avatar:
            existing.avatar_url = normalized_avatar
        if canonical_url:
            existing.canonical_url = canonical_url
        if metadata:
            existing.metadata_json = {**(existing.metadata_json or {}), **metadata}
        await session.flush()
        return existing

    source = ContentCreatorSource(
        platform=platform,
        platform_creator_id=platform_creator_id,
        username=username,
        display_name=display_name,
        profile_url=profile_url,
        avatar_url=normalized_avatar,
        avatar_checked_at=now,
        canonical_url=canonical_url,
        metadata_json=metadata or {},
        monitor_status=monitor_status,
    )
    session.add(source)
    await session.flush()
    return source
