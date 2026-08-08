"""Shared Discord embed builder.

Single source of truth for turning a normalized embed definition (the same
shape the dashboard `DiscordEmbedPayload` produces) into a Discord API embed
dict, with centralized colour parsing and Discord character limits.

All embed-producing surfaces (campaigns, role menus, embed messages, ...)
should build embeds through :func:`build_embed_dict` instead of hand-rolling
dicts so limits and colour handling stay consistent.

Convergence status / future targets (left functioning, not yet migrated):
- app/workers/campaign_worker.py .............. migrated (uses this builder).
- app/routes/embed_messages.py ................ uses this builder.
- app/services/content_notifications/payload_builder.py: has its own
  tag-resolving builder + parse_embed_color; candidate to share this later.
- app/routes/role_menus.py: builds a minimal title/description/color embed
  inline (no user media); low priority.
- Bot cogs (apps/bot/bot/{honeypot,leveling,server_logging,...}.py) build
  discord.py ``discord.Embed`` objects gateway-side (a different object model
  from this REST-dict builder) and are intentionally NOT migrated here.
"""

from __future__ import annotations

from typing import Any

# Discord embed limits (mirrors DISCORD_LIMITS in the dashboard).
DISCORD_LIMITS = {
    "content": 2000,
    "embed_title": 256,
    "embed_description": 4096,
    "embed_footer": 2048,
    "embed_fields": 25,
    "field_name": 256,
    "field_value": 1024,
    "author_name": 256,
    "total": 6000,
}

_DEFAULT_COLOR = 0x5865F2


def parse_embed_color(color: Any) -> int | None:
    """Convert a hex string (``#rrggbb``/``rrggbb``) or int into a Discord int."""
    if color is None or color == "":
        return None
    if isinstance(color, bool):  # bool is a subclass of int; reject explicitly.
        return None
    if isinstance(color, int):
        return color if 0 < color <= 0xFFFFFF else None
    if isinstance(color, str):
        raw = color.strip().lstrip("#")
        if len(raw) == 6 and all(c in "0123456789abcdefABCDEF" for c in raw):
            return int(raw, 16)
    return None


def _clean_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def build_embed_dict(
    embed: dict[str, Any] | None,
    *,
    default_color: int | None = _DEFAULT_COLOR,
    footer_suffix: str | None = None,
) -> dict[str, Any] | None:
    """Build a Discord embed dict from a normalized embed definition.

    Accepts the flat dashboard shape (``title``, ``description``, ``color``,
    ``footer``, ``footer_icon_url``, ``author`` {name/url/icon_url},
    ``thumbnail_url``, ``image_url``, ``fields``) and returns a Discord-ready
    dict truncated to Discord limits. Returns ``None`` when nothing renders.
    """
    if not isinstance(embed, dict):
        embed = {}

    out: dict[str, Any] = {}

    title = embed.get("title")
    if isinstance(title, str) and title.strip():
        out["title"] = title[: DISCORD_LIMITS["embed_title"]]

    description = embed.get("description")
    if isinstance(description, str) and description.strip():
        out["description"] = description[: DISCORD_LIMITS["embed_description"]]

    color = parse_embed_color(embed.get("color"))
    if color is None:
        color = default_color
    if color is not None:
        out["color"] = color

    author = embed.get("author")
    if isinstance(author, dict):
        name = author.get("name")
        if isinstance(name, str) and name.strip():
            author_dict: dict[str, Any] = {
                "name": name[: DISCORD_LIMITS["author_name"]]
            }
            url = _clean_url(author.get("url"))
            if url:
                author_dict["url"] = url
            icon = _clean_url(author.get("icon_url"))
            if icon:
                author_dict["icon_url"] = icon
            out["author"] = author_dict

    thumbnail = _clean_url(embed.get("thumbnail_url"))
    if thumbnail:
        out["thumbnail"] = {"url": thumbnail}

    image = _clean_url(embed.get("image_url"))
    if image:
        out["image"] = {"url": image}

    fields_in = embed.get("fields")
    if isinstance(fields_in, list):
        fields_out: list[dict[str, Any]] = []
        for raw in fields_in[: DISCORD_LIMITS["embed_fields"]]:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "")[: DISCORD_LIMITS["field_name"]]
            value = str(raw.get("value") or "")[: DISCORD_LIMITS["field_value"]]
            if not name and not value:
                continue
            fields_out.append(
                {
                    "name": name or "\u200b",
                    "value": value or "\u200b",
                    "inline": bool(raw.get("inline", False)),
                }
            )
        if fields_out:
            out["fields"] = fields_out

    footer_text = embed.get("footer")
    footer_text = footer_text if isinstance(footer_text, str) else ""
    if footer_suffix:
        footer_text = f"{footer_text} · {footer_suffix}" if footer_text else footer_suffix
    if footer_text.strip():
        footer_dict: dict[str, Any] = {
            "text": footer_text[: DISCORD_LIMITS["embed_footer"]]
        }
        footer_icon = _clean_url(embed.get("footer_icon_url"))
        if footer_icon:
            footer_dict["icon_url"] = footer_icon
        out["footer"] = footer_dict

    # An embed with only a colour renders as an empty coloured bar; treat that
    # as "nothing to show" for callers that want to fall back to plain text.
    meaningful = {k for k in out if k != "color"}
    if not meaningful:
        return None
    return out


def embed_total_characters(embed: dict[str, Any]) -> int:
    total = 0
    for key in ("title", "description"):
        value = embed.get(key)
        if isinstance(value, str):
            total += len(value)
    footer = embed.get("footer")
    if isinstance(footer, dict) and isinstance(footer.get("text"), str):
        total += len(footer["text"])
    author = embed.get("author")
    if isinstance(author, dict) and isinstance(author.get("name"), str):
        total += len(author["name"])
    for field in embed.get("fields", []) or []:
        if isinstance(field, dict):
            total += len(str(field.get("name") or ""))
            total += len(str(field.get("value") or ""))
    return total
