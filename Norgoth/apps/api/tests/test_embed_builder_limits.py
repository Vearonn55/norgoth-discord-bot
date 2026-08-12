"""Tests for the shared Discord embed builder: limits and colour parsing."""

from __future__ import annotations

from app.services.discord.embed_builder import (
    DISCORD_LIMITS,
    build_embed_dict,
    embed_total_characters,
    parse_embed_color,
)


def test_parse_embed_color_variants() -> None:
    assert parse_embed_color("#5865f2") == 0x5865F2
    assert parse_embed_color("5865f2") == 0x5865F2
    assert parse_embed_color(0x00FF00) == 0x00FF00
    assert parse_embed_color("") is None
    assert parse_embed_color(None) is None
    assert parse_embed_color("nothex") is None
    assert parse_embed_color(True) is None


def test_build_embed_truncates_to_limits() -> None:
    embed = build_embed_dict(
        {
            "title": "T" * 5000,
            "description": "D" * 5000,
            "footer": "F" * 5000,
            "color": "#123456",
            "fields": [
                {"name": "N" * 500, "value": "V" * 2000, "inline": True}
            ],
        }
    )
    assert embed is not None
    assert len(embed["title"]) == DISCORD_LIMITS["embed_title"]
    assert len(embed["description"]) == DISCORD_LIMITS["embed_description"]
    assert len(embed["footer"]["text"]) == DISCORD_LIMITS["embed_footer"]
    assert len(embed["fields"][0]["name"]) == DISCORD_LIMITS["field_name"]
    assert len(embed["fields"][0]["value"]) == DISCORD_LIMITS["field_value"]
    assert embed["color"] == 0x123456


def test_build_embed_caps_field_count() -> None:
    fields = [{"name": f"n{i}", "value": f"v{i}"} for i in range(40)]
    embed = build_embed_dict({"title": "hi", "fields": fields})
    assert embed is not None
    assert len(embed["fields"]) == DISCORD_LIMITS["embed_fields"]


def test_build_embed_returns_none_when_empty() -> None:
    # Only a colour renders as an empty coloured bar -> treated as nothing.
    assert build_embed_dict({"color": "#5865f2"}) is None
    assert build_embed_dict(None) is None
    assert build_embed_dict({}) is None


def test_build_embed_media_and_author() -> None:
    embed = build_embed_dict(
        {
            "title": "Hello",
            "author": {"name": "Bot", "icon_url": "https://x/a.png", "url": ""},
            "thumbnail_url": " https://x/t.png ",
            "image_url": "https://x/i.png",
            "footer": "base",
            "footer_icon_url": "https://x/f.png",
        }
    )
    assert embed is not None
    assert embed["author"] == {"name": "Bot", "icon_url": "https://x/a.png"}
    assert embed["thumbnail"] == {"url": "https://x/t.png"}
    assert embed["image"] == {"url": "https://x/i.png"}
    assert embed["footer"]["icon_url"] == "https://x/f.png"


def test_build_embed_omits_whitespace_urls() -> None:
    embed = build_embed_dict(
        {
            "title": "Hello",
            "author": {"name": "Bot", "icon_url": "   ", "url": "\t"},
            "thumbnail_url": " ",
            "image_url": "",
            "footer": "base",
            "footer_icon_url": "  ",
        }
    )
    assert embed is not None
    assert embed["author"] == {"name": "Bot"}
    assert "thumbnail" not in embed
    assert "image" not in embed
    assert "icon_url" not in embed["footer"]


def test_footer_suffix_appends() -> None:
    embed = build_embed_dict(
        {"title": "Hi", "footer": "Base"}, footer_suffix="Unsub"
    )
    assert embed is not None
    assert embed["footer"]["text"] == "Base · Unsub"


def test_embed_total_characters() -> None:
    embed = {
        "title": "abc",
        "description": "de",
        "footer": {"text": "fg"},
        "author": {"name": "hi"},
        "fields": [{"name": "n", "value": "vv"}],
    }
    # 3 + 2 + 2 + 2 + (1 + 2) = 12
    assert embed_total_characters(embed) == 12
