"""Unit tests for content notification tag resolution and payload building."""

from __future__ import annotations

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
)
from app.services.content_notifications.payload_builder import build_discord_payload
from app.services.content_notifications.tag_resolver import resolve_tags


def _event() -> NormalizedContentEvent:
    return NormalizedContentEvent(
        platform=PlatformType.TWITCH,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="stream-1",
        creator_platform_id="123",
        creator_name="NorgothLive",
        creator_avatar="https://example.com/a.png",
        title="Friday Night",
        content_url="https://twitch.tv/norgoth",
        playable_url="https://twitch.tv/norgoth",
        game="Just Chatting",
        viewer_count=42,
    )


def test_resolve_tags_replaces_known_placeholders() -> None:
    rendered = resolve_tags(
        "{ping_role}\n{account} is live!\n{title}\nPlaying {game}\n{link}",
        _event(),
        ping_role_id="999",
    )
    assert "<@&999>" in rendered
    assert "NorgothLive is live!" in rendered
    assert "Friday Night" in rendered
    assert "Just Chatting" in rendered
    assert "https://twitch.tv/norgoth" in rendered


def test_build_discord_payload_includes_embed_and_override() -> None:
    payload = build_discord_payload(
        content_template="{account} is live!",
        embed_template={
            "title": "{title}",
            "description": "Playing {game}",
            "color": "#6ea8fe",
        },
        event=_event(),
        username="Custom Bot",
        avatar_url="https://example.com/bot.png",
    )
    assert payload["content"] == "NorgothLive is live!"
    assert payload["username"] == "Custom Bot"
    assert payload["avatar_url"] == "https://example.com/bot.png"
    assert payload["embeds"][0]["title"] == "Friday Night"
    assert "Just Chatting" in payload["embeds"][0]["description"]
