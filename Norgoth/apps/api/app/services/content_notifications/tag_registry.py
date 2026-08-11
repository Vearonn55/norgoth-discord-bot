"""Default Norgoth notification templates and tag registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
)


@dataclass(frozen=True, slots=True)
class TagDefinition:
    name: str
    description: str
    supported_event_types: frozenset[ContentEventType]
    resolver: Callable[[NormalizedContentEvent, dict[str, str]], str]


PLATFORM_ICONS = {
    PlatformType.YOUTUBE: "▶️",
    PlatformType.TWITCH: "📺",
    PlatformType.KICK: "🟢",
    PlatformType.X: "𝕏",
    PlatformType.TIKTOK: "🎵",
}


DEFAULT_TEMPLATES: dict[PlatformType, str] = {
    PlatformType.YOUTUBE: (
        "{ping_role}\n{account} uploaded a new video!\n\n{title}\n{link}"
    ),
    PlatformType.TWITCH: (
        "{ping_role}\n{account} is now live!\n\n{title}\nPlaying {game}\n{link}"
    ),
    PlatformType.KICK: (
        "{ping_role}\n{account} is now live!\n\n{title}\nPlaying {game}\n{link}"
    ),
    PlatformType.X: "{ping_role}\nNew post from {account}\n\n{link}",
    PlatformType.TIKTOK: (
        "{ping_role}\n{account} posted new content!\n\n{link}"
    ),
}


def _or_empty(value: str | None) -> str:
    return value or ""


def build_tag_registry() -> dict[str, TagDefinition]:
    all_events = frozenset(ContentEventType)

    def account(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return event.creator_name or "Unknown creator"

    def profile_pic(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return _or_empty(event.creator_avatar)

    def link(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return _or_empty(event.content_url)

    def playable_link(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return _or_empty(event.playable_url or event.content_url)

    def ping_role(_event: NormalizedContentEvent, ctx: dict[str, str]) -> str:
        role_id = ctx.get("ping_role_id")
        return f"<@&{role_id}>" if role_id else ""

    def platform_icon(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return PLATFORM_ICONS.get(event.platform, "")

    def title(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return _or_empty(event.title)

    def game(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        return _or_empty(event.game or event.category)

    def viewers(event: NormalizedContentEvent, _ctx: dict[str, str]) -> str:
        if event.viewer_count is None:
            return ""
        return str(event.viewer_count)

    tags = [
        TagDefinition("account", "Creator display name", all_events, account),
        TagDefinition("profile_pic", "Creator avatar URL", all_events, profile_pic),
        TagDefinition("link", "Primary content URL", all_events, link),
        TagDefinition(
            "playable_link",
            "Playable/stream URL",
            all_events,
            playable_link,
        ),
        TagDefinition("ping_role", "Configured Discord role mention", all_events, ping_role),
        TagDefinition("platform_icon", "Platform emoji marker", all_events, platform_icon),
        TagDefinition("title", "Content title", all_events, title),
        TagDefinition(
            "game",
            "Game or category",
            frozenset(
                {
                    ContentEventType.STREAM_STARTED,
                    ContentEventType.STREAM_ENDED,
                    ContentEventType.VIDEO_PUBLISHED,
                }
            ),
            game,
        ),
        TagDefinition(
            "viewers",
            "Viewer count when available",
            frozenset({ContentEventType.STREAM_STARTED}),
            viewers,
        ),
    ]
    return {tag.name: tag for tag in tags}


TAG_REGISTRY = build_tag_registry()
