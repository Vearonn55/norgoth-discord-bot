"""Unit tests for content notification delivery helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
)


def _live_event(**overrides: object) -> NormalizedContentEvent:
    values: dict = dict(
        platform=PlatformType.KICK,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="42:2026-08-13T10:00:00Z",
        creator_platform_id="42",
        creator_name="Demo",
        is_live=True,
        thumbnail_url=None,
        published_at=datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return NormalizedContentEvent(**values)


@pytest.mark.anyio
async def test_refresh_live_preview_fills_missing_thumbnail() -> None:
    from app.services.content_notifications.delivery import _refresh_live_preview

    event = _live_event()
    source = MagicMock()
    source.platform = "kick"
    source.platform_creator_id = "42"
    source.username = "demo"
    source.display_name = "Demo"
    source.profile_url = "https://kick.com/demo"
    source.avatar_url = "https://example.com/a.png"

    latest_event = _live_event(
        thumbnail_url="https://images.kick.com/live.jpg",
    )
    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.fetch_latest = AsyncMock(return_value=[latest_event])

    with patch(
        "app.services.content_notifications.delivery.get_adapter",
        return_value=adapter,
    ):
        await _refresh_live_preview(
            event,
            http_client=AsyncMock(),
            source=source,
        )

    assert event.thumbnail_url == "https://images.kick.com/live.jpg"
    adapter.fetch_latest.assert_awaited_once()


@pytest.mark.anyio
async def test_refresh_live_preview_skips_when_thumbnail_present() -> None:
    from app.services.content_notifications.delivery import _refresh_live_preview

    event = _live_event(thumbnail_url="https://images.kick.com/existing.jpg")
    source = MagicMock()
    source.platform = "kick"

    with patch(
        "app.services.content_notifications.delivery.get_adapter",
    ) as get_adapter:
        await _refresh_live_preview(
            event,
            http_client=AsyncMock(),
            source=source,
        )

    get_adapter.assert_not_called()
    assert event.thumbnail_url == "https://images.kick.com/existing.jpg"


@pytest.mark.anyio
async def test_refresh_live_preview_skips_offline_event() -> None:
    from app.services.content_notifications.delivery import _refresh_live_preview

    event = _live_event(is_live=False)
    source = MagicMock()
    source.platform = "kick"

    with patch(
        "app.services.content_notifications.delivery.get_adapter",
    ) as get_adapter:
        await _refresh_live_preview(
            event,
            http_client=AsyncMock(),
            source=source,
        )

    get_adapter.assert_not_called()
