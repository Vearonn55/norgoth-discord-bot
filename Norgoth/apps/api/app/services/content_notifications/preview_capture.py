"""Capture and freeze the first official live-stream preview at stream start."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.content_platforms.registry import get_adapter
from app.integrations.content_platforms.thumbnail import (
    is_rejected_stream_preview,
    is_trusted_preview_host,
    normalize_twitch_preview_url,
    preview_requires_snapshot,
)
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
    PreviewCaptureStatus,
    ResolvedCreator,
)
from app.security.ssrf import SsrfError, safe_fetch, validate_url_syntax
from app.services.media.factory import get_media_storage
from app.services.media.service import MediaService
from app.services.uploads.image_store import UploadValidationError

logger = logging.getLogger("norgoth.content.preview")

PREVIEW_LOCK_PREFIX = "norgoth:cn:preview-capture:"
PREVIEW_LOCK_TTL_SECONDS = 60
READINESS_ATTEMPTS = 3
READINESS_BACKOFF_SECONDS = 2
PREVIEW_MAX_BODY_BYTES = 2 * 1024 * 1024


def _public_media_base_url() -> str | None:
    settings = get_settings()
    return (
        settings.aws_s3_public_base_url
        or os.getenv("NORGOTH_API_URL", "").strip()
        or None
    )


def _normalize_candidate_url(
    platform: PlatformType,
    url: str | None,
) -> str | None:
    if not url:
        return None
    trimmed = url.strip()
    if platform == PlatformType.TWITCH:
        return normalize_twitch_preview_url(trimmed)
    return trimmed or None


def resolve_embed_preview_url(event: NormalizedContentEvent) -> str | None:
    """Return the frozen preview URL for Discord embed images."""

    if event.stream_preview_url:
        return event.stream_preview_url
    if event.stream_preview_storage_key:
        storage = get_media_storage()
        public = storage.public_url(
            event.stream_preview_storage_key,
            public_base_url=_public_media_base_url(),
        )
        if public.startswith("https://"):
            return public
    if (
        event.event_type == ContentEventType.STREAM_STARTED
        and event.preview_capture_status is None
        and event.thumbnail_url
    ):
        return _normalize_candidate_url(event.platform, event.thumbnail_url)
    return None


async def _safe_fetch_trusted_preview(
    url: str,
    platform: PlatformType,
    *,
    http_client: httpx.AsyncClient,
) -> bytes | None:
    try:
        validate_url_syntax(url)
    except SsrfError:
        logger.info(
            "cn_preview_fetch_rejected platform=%s reason=invalid_url",
            platform.value,
        )
        return None
    if not is_trusted_preview_host(platform, url):
        logger.info(
            "cn_preview_fetch_rejected platform=%s reason=untrusted_host",
            platform.value,
        )
        return None
    try:
        result = await safe_fetch(
            url,
            client=http_client,
            max_body_bytes=PREVIEW_MAX_BODY_BYTES,
            headers={
                "User-Agent": "NorBot-ContentNotifications/1.0",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            },
        )
    except SsrfError as error:
        logger.info(
            "cn_preview_fetch_rejected platform=%s reason=%s",
            platform.value,
            error.code,
        )
        return None
    except httpx.HTTPError:
        logger.info(
            "cn_preview_fetch_timeout platform=%s",
            platform.value,
        )
        return None
    if result.status_code != 200:
        return None
    content_type = (result.headers.get("content-type") or "").split(";", 1)[0].strip()
    if content_type and not content_type.startswith("image/"):
        logger.info(
            "cn_preview_fetch_rejected platform=%s reason=mime",
            platform.value,
        )
        return None
    if not is_trusted_preview_host(platform, result.final_url):
        logger.info(
            "cn_preview_fetch_rejected platform=%s reason=redirect_host",
            platform.value,
        )
        return None
    return result.body


async def _snapshot_preview_url(
    url: str,
    *,
    platform: PlatformType,
    session_id: str,
    http_client: httpx.AsyncClient,
) -> tuple[str | None, str | None]:
    body = await _safe_fetch_trusted_preview(url, platform, http_client=http_client)
    if not body:
        return None, None
    try:
        stored = MediaService(get_media_storage()).upload_cn_preview(
            data=body,
            platform=platform.value,
            session_id=session_id,
            public_base_url=_public_media_base_url(),
        )
    except UploadValidationError:
        logger.info(
            "cn_preview_storage_unavailable platform=%s session_id=%s",
            platform.value,
            session_id[:32],
        )
        return None, None
    public = stored.public_url
    if not public.startswith("https://"):
        logger.info(
            "cn_preview_storage_unavailable platform=%s reason=non_public_url",
            platform.value,
        )
        return None, stored.storage_key
    return public, stored.storage_key


def _candidate_from_event(event: NormalizedContentEvent) -> str | None:
    return _normalize_candidate_url(event.platform, event.thumbnail_url)


async def _readiness_retry_fetch(
    event: NormalizedContentEvent,
    creator: ResolvedCreator,
) -> str | None:
    adapter = get_adapter(event.platform)
    if not adapter.is_available():
        return None
    try:
        latest = await adapter.fetch_latest(creator, limit=1)
    except Exception:
        logger.info(
            "cn_preview_not_ready platform=%s reason=fetch_failed",
            event.platform.value,
            exc_info=True,
        )
        return None
    if not latest:
        return None
    live = latest[0]
    if live.title and not event.title:
        event.title = live.title
    if live.game and not event.game:
        event.game = live.game
    if live.viewer_count is not None and event.viewer_count is None:
        event.viewer_count = live.viewer_count
    if live.playable_url:
        event.playable_url = live.playable_url
        event.content_url = live.content_url or live.playable_url
    if event.platform == PlatformType.TWITCH and live.external_content_id:
        event.external_content_id = live.external_content_id
    return _normalize_candidate_url(event.platform, live.thumbnail_url)


async def _acquire_preview_lock(platform: str, session_id: str) -> bool:
    from app.services.content_notifications.queue import get_redis

    redis_client = None
    try:
        redis_client = await get_redis()
        acquired = await redis_client.set(
            f"{PREVIEW_LOCK_PREFIX}{platform}:{session_id}",
            "1",
            nx=True,
            ex=PREVIEW_LOCK_TTL_SECONDS,
        )
        return bool(acquired)
    except Exception:  # noqa: BLE001
        return True
    finally:
        if redis_client is not None:
            await redis_client.aclose()


async def capture_stream_preview(
    event: NormalizedContentEvent,
    *,
    http_client: httpx.AsyncClient,
    creator: ResolvedCreator | None = None,
) -> NormalizedContentEvent:
    """Freeze the first valid live preview on ``event`` (mutates in place)."""

    if event.event_type != ContentEventType.STREAM_STARTED:
        return event

    logger.info(
        "cn_live_transition_detected platform=%s session_id=%s",
        event.platform.value,
        event.external_content_id,
    )

    if not event.stream_started_at:
        event.stream_started_at = event.published_at or datetime.now(timezone.utc)

    lock_ok = await _acquire_preview_lock(
        event.platform.value,
        event.external_content_id,
    )
    if not lock_ok:
        logger.info(
            "cn_preview_not_ready platform=%s reason=lock_busy",
            event.platform.value,
        )
        return event

    candidate = _candidate_from_event(event)
    if is_rejected_stream_preview(
        candidate,
        platform=event.platform,
        creator_avatar=event.creator_avatar,
    ):
        candidate = None

    if candidate is None and creator is not None:
        for attempt in range(READINESS_ATTEMPTS):
            if attempt:
                await asyncio.sleep(READINESS_BACKOFF_SECONDS)
            logger.info(
                "cn_preview_not_ready platform=%s attempt=%s",
                event.platform.value,
                attempt + 1,
            )
            candidate = await _readiness_retry_fetch(event, creator)
            if candidate and not is_rejected_stream_preview(
                candidate,
                platform=event.platform,
                creator_avatar=event.creator_avatar,
            ):
                event.thumbnail_url = candidate
                break
            candidate = None

    if not candidate:
        logger.info(
            "cn_image_omitted platform=%s event_type=%s reason=missing_thumbnail",
            event.platform.value,
            event.event_type.value,
        )
        event.preview_capture_status = PreviewCaptureStatus.UNAVAILABLE.value
        return event

    if is_rejected_stream_preview(
        candidate,
        platform=event.platform,
        creator_avatar=event.creator_avatar,
    ):
        logger.info(
            "cn_preview_rejected_placeholder platform=%s",
            event.platform.value,
        )
        event.preview_capture_status = PreviewCaptureStatus.REJECTED_PLACEHOLDER.value
        return event

    now = datetime.now(timezone.utc)
    if preview_requires_snapshot(event.platform, candidate):
        public_url, storage_key = await _snapshot_preview_url(
            candidate,
            platform=event.platform,
            session_id=event.external_content_id,
            http_client=http_client,
        )
        if public_url:
            event.stream_preview_url = public_url
            event.stream_preview_storage_key = storage_key
            event.preview_capture_status = PreviewCaptureStatus.CAPTURED_SNAPSHOT.value
            event.preview_captured_at = now
            logger.info(
                "cn_preview_captured platform=%s status=captured_snapshot",
                event.platform.value,
            )
            return event
        if storage_key:
            event.stream_preview_storage_key = storage_key
            event.preview_capture_status = PreviewCaptureStatus.FETCH_REJECTED.value
            return event
        event.preview_capture_status = PreviewCaptureStatus.FETCH_REJECTED.value
        return event

    event.stream_preview_url = candidate
    event.preview_capture_status = PreviewCaptureStatus.CAPTURED_URL.value
    event.preview_captured_at = now
    event.thumbnail_url = candidate
    logger.info(
        "cn_preview_captured platform=%s status=captured_url",
        event.platform.value,
    )
    return event


def creator_from_event(event: NormalizedContentEvent) -> ResolvedCreator | None:
    profile = event.content_url or event.playable_url
    if not profile:
        return None
    return ResolvedCreator(
        platform=event.platform,
        platform_creator_id=event.creator_platform_id,
        username=event.creator_name,
        display_name=event.creator_name,
        profile_url=profile,
        avatar_url=event.creator_avatar,
    )
