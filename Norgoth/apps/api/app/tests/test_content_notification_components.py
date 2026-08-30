"""Tests for live stream Discord Link button components."""

from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
)
from app.services.content_notifications.components_builder import (
    build_stream_watch_components,
)
from app.services.content_notifications.i18n import watch_on_platform_label
from app.services.content_notifications.payload_builder import build_discord_payload
from app.services.content_notifications.stream_urls import validate_canonical_stream_url


def _live_event(**overrides: object) -> NormalizedContentEvent:
    values: dict = dict(
        platform=PlatformType.TWITCH,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="stream-1",
        creator_platform_id="123",
        creator_name="NorgothLive",
        content_url="https://www.twitch.tv/norgoth",
        playable_url="https://www.twitch.tv/norgoth",
        thumbnail_url="https://static-cdn.jtvnw.net/previews-ttv/live_user_norgoth-1280x720.jpg",
        published_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return NormalizedContentEvent(**values)


def test_validate_canonical_stream_url_twitch() -> None:
    assert (
        validate_canonical_stream_url(
            PlatformType.TWITCH,
            "https://twitch.tv/norgoth",
        )
        == "https://www.twitch.tv/norgoth"
    )
    assert validate_canonical_stream_url(PlatformType.TWITCH, "javascript:alert(1)") is None


def test_validate_canonical_stream_url_youtube() -> None:
    assert (
        validate_canonical_stream_url(
            PlatformType.YOUTUBE,
            "https://youtu.be/abc12345",
            video_id="abc12345",
        )
        == "https://www.youtube.com/watch?v=abc12345"
    )


def test_build_stream_watch_components_link_style() -> None:
    components = build_stream_watch_components(_live_event(), locale="en")
    assert components is not None
    button = components[0]["components"][0]
    assert button["type"] == 2
    assert button["style"] == 5
    assert button["url"] == "https://www.twitch.tv/norgoth"
    assert "custom_id" not in button
    assert "Watch on Twitch" in button["label"]


def test_build_stream_watch_components_turkish_label() -> None:
    components = build_stream_watch_components(_live_event(), locale="tr")
    assert components is not None
    assert "Twitch'te İzle" in components[0]["components"][0]["label"]


def test_watch_on_platform_label_fallback() -> None:
    assert watch_on_platform_label(PlatformType.KICK, locale="tr") == "Kick'te İzle"


def test_build_discord_payload_includes_components_for_live() -> None:
    payload = build_discord_payload(
        content_template="{account} is live!",
        embed_template={"title": "{title}", "image_url": "{thumbnail}"},
        event=_live_event(
            stream_preview_url=(
                "https://static-cdn.jtvnw.net/previews-ttv/live_user_norgoth-1280x720.jpg"
            ),
            preview_capture_status="captured_url",
        ),
        locale="en",
    )
    assert "components" in payload
    assert payload["components"][0]["components"][0]["style"] == 5


def test_invalid_stream_url_omits_button() -> None:
    components = build_stream_watch_components(
        _live_event(content_url="https://evil.example/live", playable_url=None),
    )
    assert components is None
