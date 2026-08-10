"""Bot feed media extraction and vote suppress helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.feed_channels import (  # noqa: E402
    FeedChannelsCog,
    _primary_media_url,
)


def test_primary_media_prefers_image_attachment() -> None:
    message = SimpleNamespace(
        id=1,
        content="hello",
        attachments=[
            SimpleNamespace(
                content_type="image/png",
                filename="a.png",
                url="https://cdn.discordapp.com/attachments/1/2/a.png",
                proxy_url="https://media.discordapp.net/attachments/1/2/a.png",
            )
        ],
        embeds=[],
    )
    assert _primary_media_url(message).endswith("a.png")
    assert "media.discordapp.net" in _primary_media_url(message)


def test_primary_media_gif_attachment() -> None:
    message = SimpleNamespace(
        id=2,
        content="",
        attachments=[
            SimpleNamespace(
                content_type="image/gif",
                filename="x.gif",
                url="https://cdn.discordapp.com/attachments/1/2/x.gif",
                proxy_url=None,
            )
        ],
        embeds=[],
    )
    assert _primary_media_url(message).endswith("x.gif")


def test_primary_media_embed_image_before_thumbnail() -> None:
    message = SimpleNamespace(
        id=3,
        content="caption",
        attachments=[],
        embeds=[
            SimpleNamespace(
                image=SimpleNamespace(url="https://example.com/full.png"),
                thumbnail=SimpleNamespace(url="https://example.com/thumb.png"),
                video=None,
            )
        ],
    )
    assert _primary_media_url(message) == "https://example.com/full.png"


def test_primary_media_klipy_gifv_prefers_thumbnail_not_mp4() -> None:
    message = SimpleNamespace(
        id=6,
        content="https://klipy.com/gifs/cute-15",
        attachments=[],
        embeds=[
            SimpleNamespace(
                image=None,
                thumbnail=SimpleNamespace(
                    url="https://static.klipy.com/ii/abc/x.webp",
                    proxy_url=None,
                ),
                video=SimpleNamespace(
                    url="https://static.klipy.com/ii/abc/x.mp4",
                    proxy_url=None,
                ),
            )
        ],
    )
    assert _primary_media_url(message) == "https://static.klipy.com/ii/abc/x.webp"


def test_primary_media_klipy_content_page_fallback() -> None:
    message = SimpleNamespace(
        id=7,
        content="https://klipy.com/gifs/funny-cat",
        attachments=[],
        embeds=[],
    )
    assert _primary_media_url(message) == "https://klipy.com/gifs/funny-cat"


def test_primary_media_content_url_fallback() -> None:
    message = SimpleNamespace(
        id=4,
        content="see https://cdn.example.com/pic.webp please",
        attachments=[],
        embeds=[],
    )
    assert _primary_media_url(message) == "https://cdn.example.com/pic.webp"


def test_primary_media_none_without_media() -> None:
    message = SimpleNamespace(id=5, content="text only", attachments=[], embeds=[])
    assert _primary_media_url(message) is None


def test_vote_suppress_consume() -> None:
    cog = FeedChannelsCog.__new__(FeedChannelsCog)
    cog._suppress_vote_removes = {}
    opposite = {"kind": "unicode", "reaction": "👎", "name": "👎"}
    cog._mark_suppress_remove(1, 2, 3, opposite)
    class Emoji:
        id = None
        def __str__(self) -> str:
            return "👎"

    assert cog._consume_suppress_remove(1, 2, 3, Emoji()) is True
    assert cog._consume_suppress_remove(1, 2, 3, Emoji()) is False
