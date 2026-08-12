"""Shared helper to render an Embed Message draft gateway-side.

Features that let admins pick an existing Embed Draft (Welcome, Leave, Level-Up,
…) reference a draft by id. The API publishes a per-draft Redis snapshot at
``norgoth:guild:{guild_id}:embeds:draft:{id}`` (see
``app/routes/embed_messages.py``). This module reads that snapshot and turns it
into a ``discord.Embed`` (+ optional message content), applying the caller's
variable substitution so tokens like ``{user}`` resolve at delivery time.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import discord

# Discord embed limits (mirror of the API/dashboard constants).
_LIMITS = {
    "title": 256,
    "description": 4096,
    "footer": 2048,
    "fields": 25,
    "field_name": 256,
    "field_value": 1024,
    "author_name": 256,
    "content": 2000,
}

_DEFAULT_COLOR = 0x5865F2

Substitute = Callable[[str], str]


def embed_draft_key(guild_id: int | str, draft_id: str) -> str:
    """Redis key for a single embed draft snapshot."""

    return f"norgoth:guild:{guild_id}:embeds:draft:{draft_id}"


def _parse_color(color: Any) -> int | None:
    if color is None or color == "" or isinstance(color, bool):
        return None
    if isinstance(color, int):
        return color if 0 < color <= 0xFFFFFF else None
    if isinstance(color, str):
        raw = color.strip().lstrip("#")
        if len(raw) == 6 and all(c in "0123456789abcdefABCDEF" for c in raw):
            return int(raw, 16)
    return None


def _apply(text: Any, substitute: Substitute | None) -> str:
    if not isinstance(text, str) or not text:
        return ""
    return substitute(text) if substitute else text


def _clean_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def build_embed_from_json(
    embed_json: dict[str, Any] | None,
    substitute: Substitute | None = None,
) -> discord.Embed | None:
    """Build a ``discord.Embed`` from the normalized dashboard embed shape.

    Applies ``substitute`` to every user-facing text field and truncates to
    Discord limits. Returns ``None`` when the embed has no meaningful content.
    """

    if not isinstance(embed_json, dict):
        return None

    title = _apply(embed_json.get("title"), substitute)[: _LIMITS["title"]]
    description = _apply(embed_json.get("description"), substitute)[
        : _LIMITS["description"]
    ]
    color = _parse_color(embed_json.get("color"))

    embed = discord.Embed(
        title=title or None,
        description=description or None,
        color=color if color is not None else _DEFAULT_COLOR,
    )

    author = embed_json.get("author")
    if isinstance(author, dict):
        name = _apply(author.get("name"), substitute)[: _LIMITS["author_name"]]
        if name:
            url = _clean_url(author.get("url"))
            icon = _clean_url(author.get("icon_url"))
            embed.set_author(name=name, url=url, icon_url=icon)

    thumbnail = _clean_url(embed_json.get("thumbnail_url"))
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    image = _clean_url(embed_json.get("image_url"))
    if image:
        embed.set_image(url=image)

    fields = embed_json.get("fields")
    if isinstance(fields, list):
        for raw in fields[: _LIMITS["fields"]]:
            if not isinstance(raw, dict):
                continue
            name = _apply(raw.get("name"), substitute)[: _LIMITS["field_name"]]
            value = _apply(raw.get("value"), substitute)[: _LIMITS["field_value"]]
            if not name and not value:
                continue
            embed.add_field(
                name=name or "\u200b",
                value=value or "\u200b",
                inline=bool(raw.get("inline", False)),
            )

    footer_text = _apply(embed_json.get("footer"), substitute)[: _LIMITS["footer"]]
    if footer_text:
        embed.set_footer(
            text=footer_text,
            icon_url=_clean_url(embed_json.get("footer_icon_url")),
        )

    # An embed with only a colour renders as an empty coloured bar.
    has_content = bool(
        embed.title
        or embed.description
        or embed.fields
        or embed.author.name
        or embed.image.url
        or embed.thumbnail.url
        or (embed.footer.text if embed.footer else None)
    )
    return embed if has_content else None


async def load_embed_draft(
    state: Any,
    guild_id: int | str,
    draft_id: str,
) -> dict[str, Any] | None:
    """Return the cached draft snapshot dict, or ``None`` when absent."""

    raw = await state.redis.get(embed_draft_key(guild_id, draft_id))
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def render_embed_draft(
    state: Any,
    guild_id: int | str,
    draft_id: str,
    substitute: Substitute | None = None,
) -> tuple[str | None, discord.Embed | None]:
    """Resolve a referenced embed draft into (content, embed) for sending.

    Returns ``(None, None)`` when the draft snapshot is missing so callers can
    fall back to a plain-text message.
    """

    draft = await load_embed_draft(state, guild_id, draft_id)
    if draft is None:
        return (None, None)

    content = _apply(draft.get("content"), substitute)[: _LIMITS["content"]]
    embed = build_embed_from_json(draft.get("embed_json"), substitute)
    return (content or None, embed)
