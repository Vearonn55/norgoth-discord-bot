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
    _due_windows,
    _is_feed_refresh_due,
    _is_window_refresh_due,
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


def test_is_feed_refresh_due_prefers_next_refresh_at() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    overdue = {
        "enabled": True,
        "windows": {
            "daily": {
                "enabled": True,
                "channel_id": "1",
                "next_refresh_at": "2026-08-10T11:59:00Z",
            }
        },
    }
    pending = {
        "enabled": True,
        "windows": {
            "daily": {
                "enabled": True,
                "channel_id": "1",
                "next_refresh_at": "2026-08-10T12:30:00Z",
            }
        },
    }
    assert _is_feed_refresh_due(overdue, now=now) is True
    assert _is_window_refresh_due(overdue, "daily", now=now) is True
    assert _due_windows(overdue, now=now) == ["daily"]
    assert _is_feed_refresh_due(pending, now=now) is False
    assert _is_feed_refresh_due({"enabled": False}, now=now) is False
    # Guild-level next_refresh_at alone is not enough without an enabled window.
    assert (
        _is_feed_refresh_due(
            {"enabled": True, "next_refresh_at": "2026-08-10T11:00:00Z"},
            now=now,
        )
        is False
    )


def test_due_windows_can_include_multiple() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    config = {
        "enabled": True,
        "windows": {
            "daily": {
                "enabled": True,
                "channel_id": "1",
                "next_refresh_at": "2026-08-10T11:00:00Z",
            },
            "weekly": {
                "enabled": True,
                "channel_id": "2",
                "next_refresh_at": "2026-08-10T11:30:00Z",
            },
            "monthly": {
                "enabled": True,
                "channel_id": "3",
                "next_refresh_at": "2026-09-01T00:00:00Z",
            },
            "all_time": {"enabled": False, "channel_id": None},
        },
    }
    assert _due_windows(config, now=now) == ["daily", "weekly"]


def test_due_windows_skips_disabled_periods() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    config = {
        "enabled": True,
        "windows": {
            "daily": {
                "enabled": False,
                "channel_id": "1",
                "next_refresh_at": "2026-08-10T11:00:00Z",
            },
            "weekly": {
                "enabled": True,
                "channel_id": "2",
                "next_refresh_at": "2026-08-10T11:30:00Z",
            },
            "monthly": {
                "enabled": False,
                "channel_id": "3",
                "next_refresh_at": "2026-08-10T11:00:00Z",
            },
            "all_time": {
                "enabled": True,
                "channel_id": "4",
                "next_refresh_at": "2026-08-10T13:00:00Z",
            },
        },
    }
    assert _due_windows(config, now=now) == ["weekly"]
    assert _is_window_refresh_due(config, "daily", now=now) is False
    assert _is_window_refresh_due(config, "all_time", now=now) is False


def test_due_windows_includes_reenabled_period_only() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    config = {
        "enabled": True,
        "windows": {
            "daily": {
                "enabled": False,
                "channel_id": "1",
                "next_refresh_at": "2026-08-10T11:00:00Z",
            },
            "weekly": {
                "enabled": True,
                "channel_id": "2",
                "next_refresh_at": "2026-08-10T11:30:00Z",
            },
            "monthly": {
                "enabled": False,
                "channel_id": "3",
                "next_refresh_at": "2026-08-10T11:00:00Z",
            },
            "all_time": {
                "enabled": True,
                "channel_id": "4",
                "next_refresh_at": "2026-08-10T13:00:00Z",
            },
        },
    }
    assert _due_windows(config, now=now) == ["weekly"]
    config["windows"]["daily"]["enabled"] = True
    assert _due_windows(config, now=now) == ["daily", "weekly"]
    assert _is_window_refresh_due(config, "monthly", now=now) is False
    assert _is_window_refresh_due(config, "all_time", now=now) is False
