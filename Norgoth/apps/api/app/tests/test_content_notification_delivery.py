"""Unit tests for content notification delivery helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
    PreviewCaptureStatus,
)
from app.models.content_notifications import NormalizedContentEventRow
from app.services.content_notifications.fanout import event_from_row


def _live_event(**overrides: object) -> NormalizedContentEvent:
    values: dict = dict(
        platform=PlatformType.KICK,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="42:2026-08-13T10:00:00Z",
        creator_platform_id="42",
        creator_name="Demo",
        is_live=True,
        thumbnail_url=None,
        stream_preview_url="https://images.kick.com/frozen.jpg",
        preview_capture_status=PreviewCaptureStatus.CAPTURED_URL.value,
        published_at=datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return NormalizedContentEvent(**values)


def test_event_from_row_maps_preview_fields() -> None:
    row = NormalizedContentEventRow(
        id=uuid4(),
        platform="twitch",
        event_type="STREAM_STARTED",
        source_id=uuid4(),
        external_content_id="stream-1",
        creator_name="Demo",
        stream_preview_url="https://cdn.example.com/frozen.jpg",
        stream_preview_storage_key="cn-previews/twitch/abc/def.jpg",
        preview_capture_status="captured_snapshot",
        preview_captured_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        stream_started_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    event = event_from_row(row)
    assert event.stream_preview_url == "https://cdn.example.com/frozen.jpg"
    assert event.stream_preview_storage_key == "cn-previews/twitch/abc/def.jpg"
    assert event.preview_capture_status == "captured_snapshot"


@pytest.mark.anyio
async def test_process_job_uses_persisted_preview_without_refresh() -> None:
    from app.services.content_notifications.delivery import process_job

    event = _live_event()
    event_row = MagicMock(spec=NormalizedContentEventRow)
    subscription = MagicMock()
    subscription.guild_id = "123456789012345678"
    subscription.destination_channel_id = "987654321098765432"
    subscription.ping_role_id = None
    subscription.template = None
    subscription.sender_style = None
    subscription.notification_locale = "en"
    subscription.source = MagicMock()
    subscription.source.platform = "kick"
    subscription.source.platform_creator_id = "42"
    subscription.source.display_name = "Demo"
    subscription.source.avatar_url = None

    job = MagicMock()
    job.id = uuid4()
    job.status = "queued"
    job.attempt_count = 0
    job.subscription_id = uuid4()
    job.event_id = uuid4()

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[job, event_row])
    session.scalar = AsyncMock(return_value=subscription)
    session.flush = AsyncMock()
    session.add = MagicMock()

    with patch(
        "app.services.content_notifications.delivery.event_from_row",
        return_value=event,
    ), patch(
        "app.services.content_notifications.delivery.build_discord_payload",
    ) as build_payload, patch(
        "app.services.content_notifications.delivery.ensure_managed_webhook",
        new=AsyncMock(return_value=MagicMock()),
    ), patch(
        "app.services.content_notifications.delivery.execute_managed_webhook",
        new=AsyncMock(return_value={}),
    ):
        build_payload.return_value = {"content": "live"}
        await process_job(session, AsyncMock(), AsyncMock(), job.id)

    kwargs = build_payload.call_args.kwargs
    assert kwargs["event"].stream_preview_url == "https://images.kick.com/frozen.jpg"
    assert kwargs["locale"] == "en"
