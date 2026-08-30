"""Discord webhook payload construction for content notifications."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from app.integrations.content_platforms.thumbnail import is_trusted_preview_host
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformType,
    PreviewCaptureStatus,
)
from app.services.content_notifications.components_builder import (
    build_stream_watch_components,
)
from app.services.content_notifications.preview_capture import resolve_embed_preview_url
from app.services.content_notifications.tag_registry import (
    PLATFORM_EMBED_COLORS,
    is_legacy_stock_thumbnail,
    should_apply_platform_color,
)
from app.services.content_notifications.tag_resolver import resolve_embed, resolve_tags

logger = logging.getLogger("norgoth.content.payload")


def parse_embed_color(color: Any) -> int | None:
    if color is None or color == "":
        return None
    if isinstance(color, int):
        return color if color > 0 else None
    if isinstance(color, str):
        raw = color.strip().lstrip("#")
        if len(raw) == 6 and all(c in "0123456789abcdefABCDEF" for c in raw):
            return int(raw, 16)
    return None


def usable_image_url(url: str | None) -> str | None:
    """Return a http(s) URL suitable for Discord embed images, else None."""

    if not url or not isinstance(url, str):
        return None
    trimmed = url.strip()
    if not trimmed:
        return None
    lowered = trimmed.lower()
    if lowered.startswith("javascript:") or lowered.startswith("data:"):
        return None
    parsed = urlparse(trimmed)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return trimmed


def cache_bust_twitch_thumbnail(url: str, content_id: str) -> str:
    """Append a cache buster only on unsigned Twitch static-cdn preview URLs."""

    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "static-cdn.jtvnw.net" not in host:
        return url
    if parsed.query:
        return url
    token = (content_id or "").strip()[:80]
    if not token:
        return url
    return urlunparse(parsed._replace(query=urlencode({"t": token})))


def _resolve_image_url(
    resolved: dict[str, Any] | None,
    embed_template: dict[str, Any] | None,
    event: NormalizedContentEvent,
) -> str | None:
    candidate = None
    if event.event_type == ContentEventType.STREAM_STARTED:
        candidate = resolve_embed_preview_url(event)
    if not candidate:
        if resolved and resolved.get("image_url"):
            candidate = resolved["image_url"]
        elif is_legacy_stock_thumbnail(embed_template):
            candidate = event.thumbnail_url
    cleaned = usable_image_url(candidate)
    if cleaned is None:
        if candidate:
            logger.info(
                "cn_image_omitted platform=%s event_type=%s reason=invalid_url",
                event.platform,
                event.event_type,
            )
        return None
    captured = event.preview_capture_status in {
        PreviewCaptureStatus.CAPTURED_URL.value,
        PreviewCaptureStatus.CAPTURED_SNAPSHOT.value,
    }
    if not captured and not is_trusted_preview_host(event.platform, cleaned):
        logger.info(
            "cn_image_omitted platform=%s event_type=%s reason=untrusted_host",
            event.platform,
            event.event_type,
        )
        return None
    if (
        event.platform == PlatformType.TWITCH
        and event.preview_capture_status != PreviewCaptureStatus.CAPTURED_SNAPSHOT.value
        and not event.stream_preview_storage_key
    ):
        return cache_bust_twitch_thumbnail(cleaned, event.external_content_id)
    return cleaned


def build_discord_payload(
    *,
    content_template: str,
    embed_template: dict[str, Any] | None,
    event: NormalizedContentEvent,
    ping_role_id: str | None = None,
    username: str | None = None,
    avatar_url: str | None = None,
    locale: str | None = "en",
) -> dict[str, Any]:
    content = resolve_tags(
        content_template,
        event,
        ping_role_id=ping_role_id,
    )[:2000]

    payload: dict[str, Any] = {"content": content or None}
    if username:
        payload["username"] = username[:80]
    if avatar_url:
        payload["avatar_url"] = avatar_url

    if ping_role_id:
        payload["allowed_mentions"] = {"parse": [], "roles": [str(ping_role_id)]}
    else:
        payload["allowed_mentions"] = {"parse": []}

    resolved = resolve_embed(embed_template, event, ping_role_id=ping_role_id)
    if resolved or embed_template is None:
        embed: dict[str, Any] = {}
        resolved = resolved or {}
        if resolved.get("title"):
            embed["title"] = str(resolved["title"])[:256]

        raw_description = str((embed_template or {}).get("description") or "").strip()
        description = resolved.get("description")
        if raw_description == "{account}":
            description = None
        if description:
            embed["description"] = str(description)[:4096]

        if should_apply_platform_color(embed_template):
            platform_color = PLATFORM_EMBED_COLORS.get(event.platform)
            if platform_color is not None:
                embed["color"] = platform_color
            else:
                color = parse_embed_color(resolved.get("color"))
                if color is not None:
                    embed["color"] = color
        else:
            color = parse_embed_color(resolved.get("color"))
            if color is not None:
                embed["color"] = color

        if resolved.get("footer"):
            embed["footer"] = {"text": str(resolved["footer"])[:2048]}

        if not is_legacy_stock_thumbnail(embed_template) and resolved.get(
            "thumbnail_url"
        ):
            thumbnail = usable_image_url(resolved["thumbnail_url"])
            if thumbnail:
                embed["thumbnail"] = {"url": thumbnail}

        image_url = _resolve_image_url(resolved, embed_template, event)
        if image_url:
            embed["image"] = {"url": image_url}

        fields = list(resolved.get("fields") or [])[:25]
        category = event.game or event.category
        if category and not fields:
            fields = [{"name": "Category", "value": str(category)[:1024], "inline": True}]
        if fields:
            embed["fields"] = fields

        if event.creator_name:
            author: dict[str, Any] = {"name": event.creator_name[:256]}
            avatar = usable_image_url(event.creator_avatar)
            if avatar:
                author["icon_url"] = avatar
            profile = usable_image_url(event.content_url)
            if profile:
                author["url"] = profile
            embed.setdefault("author", author)
        if event.content_url and "url" not in embed:
            link = usable_image_url(event.content_url)
            if link:
                embed["url"] = link
        if event.published_at is not None:
            embed["timestamp"] = event.published_at.isoformat()

        if embed:
            payload["embeds"] = [embed]

    components = build_stream_watch_components(event, locale=locale)
    if components:
        payload["components"] = components

    # Discord requires at least content or embeds.
    if not payload.get("content") and not payload.get("embeds"):
        payload["content"] = event.content_url or f"{event.creator_name} — {event.event_type}"

    return payload
