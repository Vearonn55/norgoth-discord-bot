"""Delivery execution for content notification jobs."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.integrations.content_platforms.registry import get_adapter
from app.integrations.content_platforms.types import PlatformType, ResolvedCreator
from app.integrations.discord.bot_rest import DiscordBotClient
from app.models.content_notifications import (
    ContentCreatorSource,
    GuildContentSubscription,
    NormalizedContentEventRow,
    NotificationDeliveryAttempt,
    NotificationJob,
    NotificationSenderStyle,
    NotificationTemplate,
)
from app.services.content_notifications.avatar import persistable_webhook_avatar
from app.services.content_notifications.fanout import event_from_row
from app.services.content_notifications.payload_builder import build_discord_payload
from app.services.content_notifications.tag_registry import DEFAULT_TEMPLATES
from app.services.content_notifications.webhook_manager import (
    WebhookManagerError,
    ensure_managed_webhook,
    execute_managed_webhook,
)

logger = logging.getLogger("norgoth.content.delivery")

MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 10


async def _refresh_live_preview(
    event,
    *,
    http_client: httpx.AsyncClient,
    source: ContentCreatorSource | None,
) -> None:
    """Best-effort in-memory preview refresh for live events missing thumbnails."""

    if not event.is_live or event.thumbnail_url or source is None:
        return
    try:
        platform = PlatformType(source.platform)
    except ValueError:
        return
    try:
        adapter = get_adapter(platform)
    except Exception:
        return
    if not adapter.is_available():
        return
    try:
        latest = await adapter.fetch_latest(
            ResolvedCreator(
                platform=platform,
                platform_creator_id=source.platform_creator_id,
                username=source.username or source.display_name,
                display_name=source.display_name,
                profile_url=source.profile_url or "",
                avatar_url=source.avatar_url,
            ),
            limit=1,
        )
    except Exception:
        logger.info(
            "cn_delivery_preview_refresh_failed platform=%s creator_id=%s",
            source.platform,
            source.platform_creator_id,
            exc_info=True,
        )
        return
    if not latest or not latest[0].thumbnail_url:
        logger.info(
            "cn_image_omitted platform=%s event_type=%s reason=missing_thumbnail",
            event.platform,
            event.event_type,
        )
        return
    event.thumbnail_url = latest[0].thumbnail_url


def sender_webhook_identity(
    sender: NotificationSenderStyle | None,
) -> tuple[str | None, str | None]:
    """Return (username, avatar_url) overrides for Discord webhook execute."""

    if sender is None:
        return None, None
    username = sender.display_name or None
    raw = sender.avatar_url
    avatar_url = persistable_webhook_avatar(raw)
    if raw and not avatar_url:
        logger.warning(
            "cn_sender_avatar_omitted style_id=%s reason=invalid_url",
            sender.id,
        )
    return username, avatar_url


async def process_job(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    bot: DiscordBotClient,
    job_id: UUID,
) -> None:
    job = await session.get(NotificationJob, job_id)
    if job is None:
        return
    if job.status in {"succeeded", "dead"}:
        return

    job.status = "running"
    job.attempt_count += 1
    await session.flush()

    subscription = await session.scalar(
        select(GuildContentSubscription)
        .where(GuildContentSubscription.id == job.subscription_id)
        .options(
            selectinload(GuildContentSubscription.template),
            selectinload(GuildContentSubscription.sender_style),
            selectinload(GuildContentSubscription.source),
        )
    )
    event_row = await session.get(NormalizedContentEventRow, job.event_id)
    if subscription is None or event_row is None:
        job.status = "dead"
        job.last_error = "Missing subscription or event"
        await session.flush()
        return

    event = event_from_row(event_row)
    source = subscription.source
    if source:
        event.creator_platform_id = source.platform_creator_id
        if not event.creator_name:
            event.creator_name = source.display_name
        if not event.creator_avatar:
            event.creator_avatar = source.avatar_url

    await _refresh_live_preview(event, http_client=http_client, source=source)

    template = subscription.template
    content_template = (
        template.content
        if template and template.content
        else DEFAULT_TEMPLATES.get(
            PlatformType(source.platform) if source else PlatformType.YOUTUBE,
            "{account}\n{link}",
        )
    )
    embed_template = template.embed_json if template else None
    sender = subscription.sender_style
    username, avatar_url = sender_webhook_identity(sender)

    payload = build_discord_payload(
        content_template=content_template,
        embed_template=embed_template,
        event=event,
        ping_role_id=subscription.ping_role_id,
        username=username,
        avatar_url=avatar_url,
    )

    started = time.perf_counter()
    try:
        webhook = await ensure_managed_webhook(
            session,
            bot,
            guild_id=subscription.guild_id,
            channel_id=subscription.destination_channel_id,
        )
        await execute_managed_webhook(session, http_client, webhook, payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        session.add(
            NotificationDeliveryAttempt(
                job_id=job.id,
                attempt_no=job.attempt_count,
                http_status=200,
                latency_ms=latency_ms,
            )
        )
        job.status = "succeeded"
        job.latency_ms = latency_ms
        job.last_error = None
        subscription.status = "subscription_healthy"
        await session.flush()
    except WebhookManagerError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        permanent = error.code in {
            "permission_error",
            "missing",
            "invalid",
        }
        session.add(
            NotificationDeliveryAttempt(
                job_id=job.id,
                attempt_no=job.attempt_count,
                http_status=None,
                latency_ms=latency_ms,
                error_code=error.code,
                error_message=str(error),
            )
        )
        job.last_error = str(error)
        if error.code == "permission_error":
            subscription.status = "discord_permission_missing"
        elif error.code == "missing":
            subscription.status = "webhook_missing"
        await _schedule_retry_or_dead(
            session,
            job,
            permanent=permanent,
            retry_after=getattr(error, "retry_after", None),
        )
    except Exception as error:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("Delivery failed for job %s", job_id)
        session.add(
            NotificationDeliveryAttempt(
                job_id=job.id,
                attempt_no=job.attempt_count,
                latency_ms=latency_ms,
                error_code="unexpected",
                error_message=str(error)[:1000],
            )
        )
        job.last_error = str(error)[:1000]
        await _schedule_retry_or_dead(session, job, permanent=False)


async def _schedule_retry_or_dead(
    session: AsyncSession,
    job: NotificationJob,
    *,
    permanent: bool,
    retry_after: float | None = None,
) -> None:
    if permanent or job.attempt_count >= MAX_ATTEMPTS:
        job.status = "dead"
        await session.flush()
        return

    delay = BASE_BACKOFF_SECONDS * (2 ** max(0, job.attempt_count - 1))
    if retry_after is not None and retry_after > 0:
        # Honor Discord Retry-After while keeping exponential backoff as a floor.
        delay = max(delay, float(retry_after))
    job.status = "failed"
    job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    await session.flush()
    # Do not Redis-enqueue here — the creating transaction may not be committed
    # yet. The worker retry sweep requeues due failed jobs after commit.
