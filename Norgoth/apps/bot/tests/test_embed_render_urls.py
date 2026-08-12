"""Whitespace URL scrubbing in gateway embed_render."""

from __future__ import annotations

import sys
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.embed_render import build_embed_from_json  # noqa: E402


def test_build_embed_from_json_omits_whitespace_urls() -> None:
    embed = build_embed_from_json(
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
    assert embed.author.name == "Bot"
    assert embed.author.icon_url is None
    assert embed.thumbnail.url is None
    assert embed.image.url is None
    assert embed.footer.text == "base"
    assert embed.footer.icon_url is None
