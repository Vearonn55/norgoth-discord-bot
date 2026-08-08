"""Resolve notification template tags from normalized events."""

from __future__ import annotations

import re
from typing import Any

from app.integrations.content_platforms.types import NormalizedContentEvent
from app.services.content_notifications.tag_registry import TAG_REGISTRY

TAG_PATTERN = re.compile(r"\{([a-z_]+)\}")


def resolve_tags(
    template: str,
    event: NormalizedContentEvent,
    *,
    ping_role_id: str | None = None,
) -> str:
    ctx = {"ping_role_id": ping_role_id or ""}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        tag = TAG_REGISTRY.get(name)
        if tag is None:
            return match.group(0)
        if event.event_type not in tag.supported_event_types:
            return ""
        return tag.resolver(event, ctx)

    # Collapse leftover blank lines from empty optional tags.
    rendered = TAG_PATTERN.sub(replace, template)
    lines = [line.rstrip() for line in rendered.splitlines()]
    cleaned: list[str] = []
    blank_streak = 0
    for line in lines:
        if line.strip():
            blank_streak = 0
            cleaned.append(line)
        else:
            blank_streak += 1
            if blank_streak <= 1:
                cleaned.append("")
    return "\n".join(cleaned).strip()


def resolve_embed(
    embed: dict[str, Any] | None,
    event: NormalizedContentEvent,
    *,
    ping_role_id: str | None = None,
) -> dict[str, Any] | None:
    if not embed:
        return None

    out: dict[str, Any] = {}
    for key in ("title", "description", "footer", "thumbnail_url", "image_url"):
        value = embed.get(key)
        if isinstance(value, str) and value:
            out[key] = resolve_tags(value, event, ping_role_id=ping_role_id)
    if embed.get("color") is not None:
        out["color"] = embed["color"]
    fields = embed.get("fields")
    if isinstance(fields, list):
        resolved_fields = []
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            value = field.get("value")
            if not isinstance(name, str) or not isinstance(value, str):
                continue
            resolved_fields.append(
                {
                    "name": resolve_tags(name, event, ping_role_id=ping_role_id)[:256],
                    "value": resolve_tags(value, event, ping_role_id=ping_role_id)[:1024],
                    "inline": bool(field.get("inline")),
                }
            )
        if resolved_fields:
            out["fields"] = resolved_fields
    return out or None


def preview_placeholders(platform: str) -> NormalizedContentEvent:
    from app.integrations.content_platforms.types import (
        ContentEventType,
        PlatformType,
    )

    plat = PlatformType(platform) if platform in PlatformType._value2member_map_ else PlatformType.YOUTUBE
    event_type = {
        PlatformType.YOUTUBE: ContentEventType.VIDEO_PUBLISHED,
        PlatformType.TWITCH: ContentEventType.STREAM_STARTED,
        PlatformType.KICK: ContentEventType.STREAM_STARTED,
        PlatformType.X: ContentEventType.POST_PUBLISHED,
        PlatformType.TIKTOK: ContentEventType.VIDEO_PUBLISHED,
    }[plat]

    return NormalizedContentEvent(
        platform=plat,
        event_type=event_type,
        external_content_id="preview",
        creator_platform_id="preview",
        creator_name="Creator Name",
        creator_avatar="https://cdn.discordapp.com/embed/avatars/0.png",
        title="Example content title",
        description="Example description",
        content_url="https://example.com/content",
        playable_url="https://example.com/watch",
        thumbnail_url="https://cdn.discordapp.com/embed/avatars/1.png",
        is_live=event_type == ContentEventType.STREAM_STARTED,
        game="Example Game",
        category="Just Chatting",
        viewer_count=1234,
    )
