"""Build Discord webhook payloads from templates and normalized events."""

from __future__ import annotations

from typing import Any

from app.integrations.content_platforms.types import NormalizedContentEvent
from app.services.content_notifications.tag_resolver import resolve_embed, resolve_tags


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


def build_discord_payload(
    *,
    content_template: str,
    embed_template: dict[str, Any] | None,
    event: NormalizedContentEvent,
    ping_role_id: str | None = None,
    username: str | None = None,
    avatar_url: str | None = None,
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

    resolved = resolve_embed(embed_template, event, ping_role_id=ping_role_id)
    if resolved:
        embed: dict[str, Any] = {}
        if resolved.get("title"):
            embed["title"] = str(resolved["title"])[:256]
        if resolved.get("description"):
            embed["description"] = str(resolved["description"])[:4096]
        color = parse_embed_color(resolved.get("color"))
        if color is not None:
            embed["color"] = color
        if resolved.get("footer"):
            embed["footer"] = {"text": str(resolved["footer"])[:2048]}
        if resolved.get("thumbnail_url"):
            embed["thumbnail"] = {"url": resolved["thumbnail_url"]}
        elif event.thumbnail_url:
            embed["thumbnail"] = {"url": event.thumbnail_url}
        if resolved.get("image_url"):
            embed["image"] = {"url": resolved["image_url"]}
        if resolved.get("fields"):
            embed["fields"] = resolved["fields"][:25]
        if event.creator_name:
            author: dict[str, Any] = {"name": event.creator_name[:256]}
            if event.creator_avatar:
                author["icon_url"] = event.creator_avatar
            if event.content_url:
                author["url"] = event.content_url
            embed.setdefault("author", author)
        if event.content_url and "url" not in embed:
            embed["url"] = event.content_url
        payload["embeds"] = [embed]

    # Discord requires at least content or embeds.
    if not payload.get("content") and not payload.get("embeds"):
        payload["content"] = event.content_url or f"{event.creator_name} — {event.event_type}"

    return payload
