"""Inbound platform webhook endpoints (YouTube WebSub, Twitch EventSub, Kick)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.integrations.content_platforms.kick.adapter import (
    KickAdapter,
    verify_kick_signature,
)
from app.integrations.content_platforms.twitch.adapter import (
    TwitchAdapter,
    verify_twitch_signature,
)
from app.integrations.content_platforms.types import (
    ContentEventType,
    PlatformRawEvent,
    PlatformType,
    ResolvedCreator,
)
from app.integrations.content_platforms.youtube.adapter import (
    YouTubeAdapter,
    parse_websub_atom,
)
from app.models.content_notifications import (
    ContentCreatorSource,
    PlatformSubscription,
)
from app.services.content_notifications.fanout import FanoutResult, persist_and_fanout
from app.services.content_notifications.preview_capture import capture_stream_preview
from app.services.content_notifications.queue import enqueue_jobs, mark_replay
from app.security.secret_box import get_secret_box

logger = logging.getLogger("norgoth.content.webhooks")

router = APIRouter(tags=["Platform Webhooks"])


async def _fanout_content_event(
    session: AsyncSession,
    event,
    source: ContentCreatorSource,
    http_client: httpx.AsyncClient,
) -> FanoutResult:
    if event.event_type == ContentEventType.STREAM_STARTED:
        event.creator_platform_id = source.platform_creator_id
        creator = ResolvedCreator(
            platform=PlatformType(source.platform),
            platform_creator_id=source.platform_creator_id,
            username=source.username or source.display_name,
            display_name=source.display_name,
            profile_url=source.profile_url or event.content_url or "",
            avatar_url=source.avatar_url or event.creator_avatar,
        )
        event = await capture_stream_preview(
            event,
            http_client=http_client,
            creator=creator,
        )
    return await persist_and_fanout(session, event, source=source)


@router.get("/webhooks/youtube/websub")
async def youtube_websub_challenge(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_topic: str | None = Query(default=None, alias="hub.topic"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_lease_seconds: str | None = Query(default=None, alias="hub.lease_seconds"),
) -> Response:
    _ = (hub_mode, hub_topic, hub_lease_seconds)
    if hub_challenge is None:
        raise HTTPException(status_code=400, detail="Missing hub.challenge")
    return Response(content=hub_challenge, media_type="text/plain")


@router.post("/webhooks/youtube/websub")
async def youtube_websub_notify(
    request: Request,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    body = await request.body()
    try:
        raw_events = parse_websub_atom(body.decode("utf-8", errors="ignore"))
    except Exception as error:  # noqa: BLE001
        logger.warning("Invalid YouTube Atom payload: %s", error)
        return {"ok": True, "ignored": True}

    adapter = YouTubeAdapter()
    job_ids: list[str] = []
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        for raw in raw_events:
            source = await session.scalar(
                select(ContentCreatorSource).where(
                    ContentCreatorSource.platform == PlatformType.YOUTUBE.value,
                    ContentCreatorSource.platform_creator_id == raw.platform_creator_id,
                )
            )
            if source is None:
                continue
            if source.display_name:
                raw.raw["creator_name"] = source.display_name
            if source.avatar_url:
                raw.raw["creator_avatar"] = source.avatar_url
            event = await adapter.enrich_event(raw)
            result = await _fanout_content_event(session, event, source, http_client)
            job_ids.extend(str(job_id) for job_id in result.job_ids)
    await session.commit()
    await enqueue_jobs(job_ids)
    return {"ok": True}


@router.post("/webhooks/twitch/eventsub", response_model=None)
async def twitch_eventsub(
    request: Request,
    session: AsyncSession = Depends(get_database_session),
) -> Response | dict[str, Any]:
    body = await request.body()
    message_id = request.headers.get("Twitch-Eventsub-Message-Id", "")
    message_type = request.headers.get("Twitch-Eventsub-Message-Type", "")
    timestamp = request.headers.get("Twitch-Eventsub-Message-Timestamp", "")
    signature = request.headers.get("Twitch-Eventsub-Message-Signature", "")

    secret = os.getenv("TWITCH_EVENTSUB_SECRET", "").strip()
    # Prefer per-subscription secret if present in DB.
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON") from error

    subscription = payload.get("subscription") or {}
    sub_id = subscription.get("id")
    if sub_id:
        row = await session.scalar(
            select(PlatformSubscription).where(
                PlatformSubscription.external_subscription_id == str(sub_id)
            )
        )
        box = get_secret_box()
        if row and row.callback_secret_encrypted and box:
            try:
                secret = box.decrypt(row.callback_secret_encrypted)
            except Exception:  # noqa: BLE001
                pass

    if not secret or not signature:
        raise HTTPException(status_code=403, detail="Twitch signature required")
    if not verify_twitch_signature(
        secret=secret,
        message_id=message_id,
        timestamp=timestamp,
        body=body,
        signature=signature,
    ):
        raise HTTPException(status_code=403, detail="Invalid Twitch signature")

    if message_type == "webhook_callback_verification":
        challenge = payload.get("challenge", "")
        return Response(content=challenge, media_type="text/plain")

    if message_type == "revocation":
        return {"ok": True}

    if message_id and not await mark_replay(f"twitch:{message_id}"):
        return {"ok": True, "deduplicated": True}

    event_data = payload.get("event") or {}
    broadcaster_id = str(event_data.get("broadcaster_user_id") or "")
    stream_id = str(event_data.get("id") or message_id)
    source = await session.scalar(
        select(ContentCreatorSource).where(
            ContentCreatorSource.platform == PlatformType.TWITCH.value,
            ContentCreatorSource.platform_creator_id == broadcaster_id,
        )
    )
    if source is None:
        return {"ok": True, "ignored": True}

    sub_type = str(subscription.get("type") or "")
    event_type = (
        ContentEventType.STREAM_ENDED
        if sub_type == "stream.offline"
        else ContentEventType.STREAM_STARTED
    )
    adapter = TwitchAdapter()
    raw = PlatformRawEvent(
        platform=PlatformType.TWITCH,
        event_type=event_type,
        external_content_id=stream_id,
        platform_creator_id=broadcaster_id,
        raw=payload,
    )
    event = await adapter.enrich_event(raw)
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        result = await _fanout_content_event(session, event, source, http_client)
    await session.commit()
    await enqueue_jobs(result.job_ids)
    return {"ok": True}


@router.post("/webhooks/kick/events")
async def kick_events(
    request: Request,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    body = await request.body()
    message_id = request.headers.get("Kick-Event-Message-Id", "")
    timestamp = request.headers.get("Kick-Event-Message-Timestamp", "")
    signature = request.headers.get("Kick-Event-Signature", "")
    event_type = request.headers.get("Kick-Event-Type", "")

    adapter = KickAdapter()
    try:
        public_key = await adapter.get_public_key()
    except Exception as error:  # noqa: BLE001
        logger.warning("Kick public key fetch failed: %s", error)
        raise HTTPException(status_code=503, detail="Kick signature verification unavailable") from error

    if not signature or not public_key:
        raise HTTPException(status_code=403, detail="Kick signature required")
    ok = await verify_kick_signature(
        message_id=message_id,
        timestamp=timestamp,
        body=body,
        signature_b64=signature,
        public_key_pem=public_key,
    )
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid Kick signature")

    if message_id and not await mark_replay(f"kick:{message_id}"):
        return {"ok": True, "deduplicated": True}

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON") from error

    if event_type != "livestream.status.updated":
        return {"ok": True, "ignored": True}

    is_live = bool(payload.get("is_live"))
    broadcaster = payload.get("broadcaster") or {}
    creator_id = str(broadcaster.get("user_id") or "")
    source = await session.scalar(
        select(ContentCreatorSource).where(
            ContentCreatorSource.platform == PlatformType.KICK.value,
            ContentCreatorSource.platform_creator_id == creator_id,
        )
    )
    if source is None:
        return {"ok": True, "ignored": True}

    raw = PlatformRawEvent(
        platform=PlatformType.KICK,
        event_type=(
            ContentEventType.STREAM_STARTED
            if is_live
            else ContentEventType.STREAM_ENDED
        ),
        external_content_id=(
            f"{creator_id}:{payload.get('started_at') or payload.get('ended_at') or message_id}"
        ),
        platform_creator_id=creator_id,
        raw=payload,
    )
    event = await adapter.enrich_event(raw)
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        result = await _fanout_content_event(session, event, source, http_client)
    await session.commit()
    await enqueue_jobs(result.job_ids)
    return {"ok": True}
