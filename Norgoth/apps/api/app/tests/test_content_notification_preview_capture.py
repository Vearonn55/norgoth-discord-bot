"""Tests for stream preview capture and frozen embed URLs."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.integrations.content_platforms.thumbnail import (
    is_rejected_stream_preview,
    preview_requires_snapshot,
)
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
    PreviewCaptureStatus,
    ResolvedCreator,
)
from app.services.content_notifications.preview_capture import (
    capture_stream_preview,
    resolve_embed_preview_url,
)


def _tiny_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(120, 80, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def _live_event(**overrides: object) -> NormalizedContentEvent:
    values: dict = dict(
        platform=PlatformType.TWITCH,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="stream-99",
        creator_platform_id="123",
        creator_name="Demo",
        is_live=True,
        content_url="https://www.twitch.tv/demo",
        playable_url="https://www.twitch.tv/demo",
        thumbnail_url=(
            "https://static-cdn.jtvnw.net/previews-ttv/live_user_demo-1280x720.jpg"
        ),
        published_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return NormalizedContentEvent(**values)


def test_is_rejected_stream_preview_flags_offline_and_avatar() -> None:
    assert is_rejected_stream_preview(
        "https://static-cdn.jtvnw.net/previews-ttv/live_user_x-440x248.jpg",
        platform=PlatformType.TWITCH,
        creator_avatar="https://static-cdn.jtvnw.net/jtv_user_pictures/x.png",
    ) is False
    assert is_rejected_stream_preview(
        "https://static-cdn.jtvnw.net/previews-ttv/live_user_x-440x248.jpg",
        platform=PlatformType.TWITCH,
        creator_avatar=(
            "https://static-cdn.jtvnw.net/previews-ttv/live_user_x-440x248.jpg"
        ),
    ) is True
    assert is_rejected_stream_preview(
        "https://static-cdn.jtvnw.net/previews-ttv/preview-404.jpg",
        platform=PlatformType.TWITCH,
    ) is True


def test_preview_requires_snapshot_twitch_and_signed_kick() -> None:
    assert preview_requires_snapshot(
        PlatformType.TWITCH,
        "https://static-cdn.jtvnw.net/previews-ttv/live_user_demo-1280x720.jpg",
    )
    assert preview_requires_snapshot(
        PlatformType.KICK,
        "https://images.kick.com/live.jpg?sig=abc",
    )
    assert not preview_requires_snapshot(
        PlatformType.YOUTUBE,
        "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
    )


def test_resolve_embed_preview_url_prefers_frozen_fields() -> None:
    event = _live_event(
        stream_preview_url="https://cdn.example.com/frozen.jpg",
        preview_capture_status=PreviewCaptureStatus.CAPTURED_URL.value,
        thumbnail_url="https://static-cdn.jtvnw.net/other.jpg",
    )
    assert resolve_embed_preview_url(event) == "https://cdn.example.com/frozen.jpg"


@pytest.mark.anyio
async def test_capture_stream_preview_snapshots_twitch(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NORGOTH_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("NORGOTH_API_URL", "https://api.example.com")

    event = _live_event()
    body = _tiny_png_bytes()
    fetch_result = MagicMock()
    fetch_result.status_code = 200
    fetch_result.headers = {"content-type": "image/png"}
    fetch_result.body = body
    fetch_result.final_url = event.thumbnail_url

    with patch(
        "app.services.content_notifications.preview_capture._acquire_preview_lock",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.content_notifications.preview_capture.safe_fetch",
        new=AsyncMock(return_value=fetch_result),
    ):
        result = await capture_stream_preview(
            event,
            http_client=AsyncMock(),
            creator=ResolvedCreator(
                platform=PlatformType.TWITCH,
                platform_creator_id="123",
                username="demo",
                display_name="Demo",
                profile_url="https://www.twitch.tv/demo",
            ),
        )

    assert result.preview_capture_status == PreviewCaptureStatus.CAPTURED_SNAPSHOT.value
    assert result.stream_preview_storage_key
    assert result.stream_preview_url.startswith("https://api.example.com/uploads/")


@pytest.mark.anyio
async def test_capture_stream_preview_youtube_persists_url_only() -> None:
    event = _live_event(
        platform=PlatformType.YOUTUBE,
        external_content_id="vid123",
        thumbnail_url="https://i.ytimg.com/vi/vid123/hqdefault.jpg",
        content_url="https://www.youtube.com/watch?v=vid123",
        playable_url="https://www.youtube.com/watch?v=vid123",
    )
    with patch(
        "app.services.content_notifications.preview_capture._acquire_preview_lock",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.content_notifications.preview_capture._snapshot_preview_url",
        new=AsyncMock(),
    ) as snapshot:
        result = await capture_stream_preview(
            event,
            http_client=AsyncMock(),
            creator=None,
        )
    snapshot.assert_not_called()
    assert result.preview_capture_status == PreviewCaptureStatus.CAPTURED_URL.value
    assert result.stream_preview_url == event.thumbnail_url


@pytest.mark.anyio
async def test_capture_stream_preview_unavailable_without_thumbnail() -> None:
    event = _live_event(thumbnail_url=None)
    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.fetch_latest = AsyncMock(return_value=[])

    with patch(
        "app.services.content_notifications.preview_capture._acquire_preview_lock",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.content_notifications.preview_capture.get_adapter",
        return_value=adapter,
    ):
        result = await capture_stream_preview(
            event,
            http_client=AsyncMock(),
            creator=ResolvedCreator(
                platform=PlatformType.TWITCH,
                platform_creator_id="123",
                username="demo",
                display_name="Demo",
                profile_url="https://www.twitch.tv/demo",
            ),
        )

    assert result.preview_capture_status == PreviewCaptureStatus.UNAVAILABLE.value
    assert result.stream_preview_url is None
