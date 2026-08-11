"""Honeypot warning embed uses shared full embed builder."""

from __future__ import annotations

import sys
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.honeypot import HoneypotCog  # noqa: E402


def test_build_warning_embed_maps_full_payload() -> None:
    cog = object.__new__(HoneypotCog)
    embed = HoneypotCog.build_warning_embed(
        cog,
        {
            "warning_embed": {
                "title": "Trap",
                "description": "**Stay out**",
                "color": "#ff9900",
                "footer": "Norgoth",
                "footer_icon_url": "https://cdn.example/icon.png",
                "thumbnail_url": "https://cdn.example/thumb.png",
                "image_url": "https://cdn.example/image.png",
                "author": {"name": "Guard", "icon_url": "https://cdn.example/a.png"},
                "fields": [{"name": "Rule", "value": "No posts", "inline": True}],
            }
        },
    )
    assert embed is not None
    assert embed.title == "Trap"
    assert embed.description == "**Stay out**"
    assert embed.colour.value == 0xFF9900
    assert embed.author.name == "Guard"
    assert embed.thumbnail.url == "https://cdn.example/thumb.png"
    assert embed.image.url == "https://cdn.example/image.png"
    assert embed.footer.text == "Norgoth"
    assert len(embed.fields) == 1
    assert embed.fields[0].name == "Rule"


def test_build_warning_embed_empty_returns_none() -> None:
    cog = object.__new__(HoneypotCog)
    assert HoneypotCog.build_warning_embed(cog, {"warning_embed": None}) is None
    assert HoneypotCog.build_warning_embed(cog, {"warning_embed": {}}) is None
