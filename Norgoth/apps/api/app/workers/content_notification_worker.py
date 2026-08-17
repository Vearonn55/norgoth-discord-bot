"""Content notification delivery worker.

Run:
  python -m app.workers.content_notification_worker
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
from dotenv import load_dotenv
from sqlalchemy import or_, select

# Local monorepo: Norgoth/apps/api/app/workers/… -> parents[4] == Norgoth/
# Docker image layout is shallower (/app/app/workers/…); compose injects env.
_here = Path(__file__).resolve()
if len(_here.parents) > 4:
    load_dotenv(_here.parents[4] / ".env")
load_dotenv()


from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.integrations.content_platforms.registry import get_adapter  # noqa: E402
from app.integrations.content_platforms.types import PlatformType  # noqa: E402
from app.integrations.discord.bot_rest import DiscordBotClient  # noqa: E402
from app.models.content_notifications import (  # noqa: E402
    ContentCreatorSource,
    NotificationJob,
    PlatformMonitorCursor,
    PlatformSubscription,
)
from app.services.content_notifications.delivery import process_job  # noqa: E402
from app.services.content_notifications.fanout import (  # noqa: E402
    ensure_source,
    persist_and_fanout,
)
from app.services.content_notifications.queue import (  # noqa: E402
    enqueue_jobs,
    heartbeat,
    is_circuit_open,
    open_circuit,
    pop_job,
)
from app.integrations.content_platforms.types import ResolvedCreator  # noqa: E402

logger = logging.getLogger("norgoth.content.worker")


async def process_due_retries(session_factory) -> None:
    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        jobs = (
            await session.scalars(
                select(NotificationJob).where(
                    NotificationJob.status == "failed",
                    NotificationJob.next_attempt_at.is_not(None),
                    NotificationJob.next_attempt_at <= now,
                ).limit(20)
            )
        ).all()
        job_ids: list[str] = []
        for job in jobs:
            job.status = "queued"
            job_ids.append(str(job.id))
        await session.commit()
        await enqueue_jobs(job_ids)


async def poll_due_sources(session_factory, http_client: httpx.AsyncClient) -> None:
    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        cursors = (
            await session.scalars(
                select(PlatformMonitorCursor)
                .where(
                    or_(
                        PlatformMonitorCursor.next_check_at.is_(None),
                        PlatformMonitorCursor.next_check_at <= now,
                    )
                )
                .limit(10)
            )
        ).all()
        job_ids: list[str] = []
        for cursor in cursors:
            source = await session.get(ContentCreatorSource, cursor.source_id)
            if source is None:
                continue
            if await is_circuit_open(source.platform):
                continue
            from app.services.content_notifications.rate_limit import throttle

            await throttle(source.platform)
            adapter = get_adapter(source.platform)
            if not adapter.is_available():
                continue
            try:
                creator = ResolvedCreator(
                    platform=PlatformType(source.platform),
                    platform_creator_id=source.platform_creator_id,
                    username=source.username,
                    display_name=source.display_name,
                    profile_url=source.profile_url,
                    avatar_url=source.avatar_url,
                    canonical_url=source.canonical_url,
                )
                events = await adapter.fetch_latest(creator, limit=3)
                for event in events:
                    if (
                        cursor.last_seen_content_id
                        and event.external_content_id == cursor.last_seen_content_id
                    ):
                        continue
                    result = await persist_and_fanout(session, event, source=source)
                    job_ids.extend(str(job_id) for job_id in result.job_ids)
                    cursor.last_seen_content_id = event.external_content_id
                cursor.failure_count = 0
                from datetime import timedelta
                import random

                jitter = random.randint(30, 120)
                cursor.next_check_at = now + timedelta(seconds=180 + jitter)
            except Exception:  # noqa: BLE001
                logger.exception("Poll failed for source %s", source.id)
                cursor.failure_count += 1
                if cursor.failure_count >= 5:
                    await open_circuit(source.platform, ttl_seconds=300)
                from datetime import timedelta

                cursor.next_check_at = now + timedelta(seconds=300)
        await session.commit()
        await enqueue_jobs(job_ids)


async def renew_websub_leases(session_factory) -> None:
    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        from datetime import timedelta

        soon = now + timedelta(hours=12)
        subs = (
            await session.scalars(
                select(PlatformSubscription).where(
                    PlatformSubscription.transport == "websub",
                    or_(
                        PlatformSubscription.lease_expires_at.is_(None),
                        PlatformSubscription.lease_expires_at <= soon,
                    ),
                ).limit(20)
            )
        ).all()
        for sub in subs:
            source = await session.get(ContentCreatorSource, sub.source_id)
            if source is None:
                continue
            adapter = get_adapter(source.platform)
            creator = ResolvedCreator(
                platform=PlatformType(source.platform),
                platform_creator_id=source.platform_creator_id,
                username=source.username,
                display_name=source.display_name,
                profile_url=source.profile_url,
                avatar_url=source.avatar_url,
            )
            result = await adapter.subscribe(creator)
            if result:
                sub.last_reconciled_at = now
                sub.lease_expires_at = now + timedelta(days=5)
                sub.failure_count = 0
            else:
                sub.failure_count += 1
        await session.commit()


async def backfill_null_avatars(session_factory) -> None:
    """Refresh a bounded batch of sources that never stored a profile image."""

    from app.services.content_notifications.avatar import (
        AVATAR_REFRESH_PER_REQUEST,
        FUNCTIONAL_PLATFORMS,
        refresh_stale_avatars,
    )

    async with session_factory() as session:
        sources = (
            await session.scalars(
                select(ContentCreatorSource)
                .where(
                    ContentCreatorSource.avatar_url.is_(None),
                    ContentCreatorSource.platform.in_(tuple(FUNCTIONAL_PLATFORMS)),
                )
                .limit(AVATAR_REFRESH_PER_REQUEST)
            )
        ).all()
        if not sources:
            return
        await refresh_stale_avatars(session, sources)
        await session.commit()


async def worker_loop() -> None:
    settings = get_settings()
    configure = logging.getLogger()
    logging.basicConfig(level=settings.log_level)

    if not settings.database_url:
        raise RuntimeError("NORGOTH_DATABASE_URL is required for content notification worker")
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required for content notification worker")

    session_factory = get_session_factory()
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        logger.info("Content notification worker started")
        ticks = 0
        while True:
            await heartbeat()
            ticks += 1
            job_id = await pop_job(timeout_seconds=2)
            if job_id:
                async with session_factory() as session:
                    try:
                        # Brief retry if the producer committed just after enqueue.
                        job_uuid = UUID(job_id)
                        for attempt in range(3):
                            job = await session.get(NotificationJob, job_uuid)
                            if job is not None:
                                break
                            await asyncio.sleep(0.15 * (attempt + 1))
                        await process_job(
                            session,
                            http_client,
                            bot,
                            job_uuid,
                        )
                        await session.commit()
                    except Exception:  # noqa: BLE001
                        logger.exception("Job %s failed", job_id)
                        await session.rollback()

            if ticks % 15 == 0:
                try:
                    await process_due_retries(session_factory)
                except Exception:  # noqa: BLE001
                    logger.exception("Retry sweep failed")

            if ticks % 30 == 0:
                try:
                    await poll_due_sources(session_factory, http_client)
                except Exception:  # noqa: BLE001
                    logger.exception("Poll sweep failed")

            if ticks % 120 == 0:
                try:
                    await renew_websub_leases(session_factory)
                except Exception:  # noqa: BLE001
                    logger.exception("Lease renewal failed")

            if ticks % 60 == 0:
                try:
                    await backfill_null_avatars(session_factory)
                except Exception:  # noqa: BLE001
                    logger.exception("Avatar backfill failed")


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
