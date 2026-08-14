"""Unit tests for content notification tag resolution and payload building."""

from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
)
from app.services.content_notifications.payload_builder import (
    build_discord_payload,
    cache_bust_twitch_thumbnail,
    usable_image_url,
)
from app.services.content_notifications.tag_registry import (
    PLATFORM_EMBED_COLORS,
    TAG_REGISTRY,
    default_embed_json,
)
from app.services.content_notifications.tag_resolver import resolve_tags


def _event(**overrides: object) -> NormalizedContentEvent:
    values: dict = dict(
        platform=PlatformType.TWITCH,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="stream-1",
        creator_platform_id="123",
        creator_name="NorgothLive",
        creator_avatar="https://example.com/a.png",
        title="Friday Night",
        content_url="https://twitch.tv/norgoth",
        playable_url="https://twitch.tv/norgoth",
        thumbnail_url="https://static-cdn.jtvnw.net/previews-ttv/live_user_norgoth-1280x720.jpg",
        game="Just Chatting",
        viewer_count=42,
        published_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return NormalizedContentEvent(**values)


STOCK_TEMPLATE = {
    "title": "{title}",
    "description": "{account}",
    "color": "#6ea8fe",
    "thumbnail_url": "{profile_pic}",
}


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


def test_thumbnail_tag_resolves_preview_url() -> None:
    assert "thumbnail" in TAG_REGISTRY
    rendered = resolve_tags("{thumbnail}", _event())
    assert "static-cdn.jtvnw.net" in rendered


def test_build_discord_payload_includes_embed_and_override() -> None:
    payload = build_discord_payload(
        content_template="{account} is live!",
        embed_template={
            "title": "{title}",
            "description": "Playing {game}",
            "color": "#ff00aa",
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
    assert payload["embeds"][0]["color"] == 0xFF00AA


def test_stock_template_uses_large_image_and_platform_color() -> None:
    payload = build_discord_payload(
        content_template="{account} is now live!\n{link}",
        embed_template=STOCK_TEMPLATE,
        event=_event(),
        ping_role_id="999",
    )
    embed = payload["embeds"][0]
    assert embed["title"] == "Friday Night"
    assert "description" not in embed
    assert embed["color"] == PLATFORM_EMBED_COLORS[PlatformType.TWITCH]
    assert "thumbnail" not in embed
    assert embed["image"]["url"].startswith(
        "https://static-cdn.jtvnw.net/previews-ttv/"
    )
    assert "t=stream-1" in embed["image"]["url"]
    assert embed["author"]["icon_url"] == "https://example.com/a.png"
    assert embed["fields"][0]["name"] == "Category"
    assert embed["fields"][0]["value"] == "Just Chatting"
    assert payload["allowed_mentions"] == {"parse": [], "roles": ["999"]}


def test_omits_image_when_thumbnail_missing_or_invalid() -> None:
    payload = build_discord_payload(
        content_template="{account}",
        embed_template=STOCK_TEMPLATE,
        event=_event(thumbnail_url=""),
    )
    assert "image" not in payload["embeds"][0]

    payload = build_discord_payload(
        content_template="{account}",
        embed_template=STOCK_TEMPLATE,
        event=_event(thumbnail_url="javascript:alert(1)"),
    )
    embed = payload["embeds"][0]
    assert "image" not in embed
    assert embed.get("image") != {"url": ""}


def test_platform_colors_and_youtube_thumbnail() -> None:
    youtube = build_discord_payload(
        content_template="{account} uploaded a new video!\n{link}",
        embed_template=STOCK_TEMPLATE,
        event=_event(
            platform=PlatformType.YOUTUBE,
            event_type=ContentEventType.VIDEO_PUBLISHED,
            thumbnail_url="https://i.ytimg.com/vi/abc123/hqdefault.jpg",
            game=None,
        ),
    )
    assert youtube["embeds"][0]["color"] == PLATFORM_EMBED_COLORS[PlatformType.YOUTUBE]
    assert youtube["embeds"][0]["image"]["url"] == (
        "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    )

    x_payload = build_discord_payload(
        content_template="New post from {account}\n{link}",
        embed_template=STOCK_TEMPLATE,
        event=_event(
            platform=PlatformType.X,
            event_type=ContentEventType.POST_PUBLISHED,
            thumbnail_url=None,
            game=None,
        ),
    )
    assert x_payload["embeds"][0]["color"] == PLATFORM_EMBED_COLORS[PlatformType.X]
    assert "image" not in x_payload["embeds"][0]


def test_new_default_embed_json_uses_thumbnail_tag() -> None:
    embed = default_embed_json(PlatformType.KICK)
    assert embed["image_url"] == "{thumbnail}"
    assert embed["color"] == "#53fc18"
    payload = build_discord_payload(
        content_template="{account} is now live!\n{link}",
        embed_template=embed,
        event=_event(
            platform=PlatformType.KICK,
            thumbnail_url="https://kick.com/thumbs/live.jpg",
        ),
    )
    assert payload["embeds"][0]["color"] == PLATFORM_EMBED_COLORS[PlatformType.KICK]
    assert payload["embeds"][0]["image"]["url"] == "https://kick.com/thumbs/live.jpg"


def test_usable_image_url_rejects_empty_and_non_http() -> None:
    assert usable_image_url("") is None
    assert usable_image_url("   ") is None
    assert usable_image_url("javascript:void(0)") is None
    assert usable_image_url("https://example.com/a.png") == "https://example.com/a.png"


def test_twitch_cache_bust_only_on_static_cdn() -> None:
    twitch = cache_bust_twitch_thumbnail(
        "https://static-cdn.jtvnw.net/previews-ttv/live.jpg",
        "stream-1",
    )
    assert twitch.endswith("?t=stream-1")
    signed = "https://images.kick.com/foo.jpg?sig=abc"
    assert cache_bust_twitch_thumbnail(signed, "x") == signed


def test_managed_webhook_matches_legacy_and_norbot_names() -> None:
    from app.services.content_notifications.webhook_manager import (
        MANAGED_WEBHOOK_NAMES,
        NORBOT_WEBHOOK_NAME,
        NORGOTH_WEBHOOK_NAME,
    )

    assert NORBOT_WEBHOOK_NAME == "NorBot Notifications"
    assert NORGOTH_WEBHOOK_NAME == "Norgoth Notifications"
    assert MANAGED_WEBHOOK_NAMES == {
        "NorBot Notifications",
        "Norgoth Notifications",
    }
