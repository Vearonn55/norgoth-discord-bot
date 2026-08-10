"""Feed rebuild helpers: ordering, capacity, media embeds, no placeholders."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.feed_rebuild import (
    build_feed_embed,
    desired_source_ids,
    needs_full_rebuild,
)
from app.services.feed_ranking import (
    clamp_display_limit,
    clamp_refresh_interval_minutes,
    merge_feed_config,
)


def _msg(
    message_id: str,
    *,
    net: int = 1,
    up: int = 1,
    down: int = 0,
    media: str | None = None,
    excerpt: str = "hello",
    author_display_name: str | None = "Alice",
    author_avatar_url: str | None = "https://cdn.discordapp.com/avatars/3/a.png",
) -> SimpleNamespace:
    return SimpleNamespace(
        guild_id="1",
        channel_id="2",
        message_id=message_id,
        author_id="3",
        author_display_name=author_display_name,
        author_avatar_url=author_avatar_url,
        content_excerpt=excerpt,
        primary_media_url=media,
        upvote_count=up,
        downvote_count=down,
        net_score=net,
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        attachment_count=1 if media else 0,
    )


def test_desired_source_ids_best_first() -> None:
    # top is best-first (A=100, B=80, C=50) → send A, B, C (#1 at top)
    top = [
        _msg("A", net=100),
        _msg("B", net=80),
        _msg("C", net=50),
    ]
    assert desired_source_ids(top) == ["A", "B", "C"]  # type: ignore[arg-type]


def test_capacity_clamp() -> None:
    assert clamp_display_limit(40) == 25
    assert clamp_display_limit(0) == 1
    assert clamp_display_limit(10) == 10


def test_refresh_interval_clamp_and_snap() -> None:
    assert clamp_refresh_interval_minutes(1) == 5
    assert clamp_refresh_interval_minutes(100) == 60
    assert clamp_refresh_interval_minutes(17) == 15
    assert clamp_refresh_interval_minutes(18) == 20
    merged = merge_feed_config({"refresh_interval_minutes": 7})
    assert merged["refresh_interval_minutes"] == 5


def test_build_feed_embed_includes_image_not_raw_only() -> None:
    msg = _msg(
        "99",
        net=5,
        media="https://cdn.discordapp.com/attachments/1/2/photo.png",
        excerpt="caption",
    )
    payload = build_feed_embed(
        rank=1,
        message=msg,  # type: ignore[arg-type]
        upvote_emoji="👍",
        downvote_emoji="👎",
        window="daily",
    )
    embed = payload["embeds"][0]
    assert embed["title"] == "#1 Trending"
    assert "Net" not in embed["title"]
    assert embed["image"]["url"].endswith("photo.png")
    assert "caption" in embed["description"]
    assert "View Original Message" in embed["description"]
    assert embed["author"]["name"] == "Alice"
    assert "Daily" in embed["footer"]["text"]
    assert "Net 5" in embed["footer"]["text"]
    assert "empty slot" not in embed["title"].lower()


def test_build_feed_embed_strips_gif_url_from_description() -> None:
    gif = "https://media.tenor.com/abc/funny.gif"
    msg = _msg("gif1", media=gif, excerpt=f"lol {gif}")
    payload = build_feed_embed(
        rank=1,
        message=msg,  # type: ignore[arg-type]
        upvote_emoji="👍",
        downvote_emoji="👎",
    )
    embed = payload["embeds"][0]
    assert embed["image"]["url"] == gif
    assert gif not in embed["description"]
    assert "lol" in embed["description"]


def test_build_feed_embed_rewrites_media_discordapp_host() -> None:
    media = "https://media.discordapp.net/attachments/1/2/pic.png?ex=1"
    msg = _msg("img1", media=media, excerpt="")
    payload = build_feed_embed(
        rank=1,
        message=msg,  # type: ignore[arg-type]
        upvote_emoji="👍",
        downvote_emoji="👎",
    )
    embed = payload["embeds"][0]
    assert embed["image"]["url"].startswith(
        "https://cdn.discordapp.com/attachments/1/2/pic.png"
    )
    assert "media.discordapp.net" not in embed["image"]["url"]


def test_primary_media_from_discord_payload_prefers_proxy() -> None:
    from app.services.feed_rebuild import primary_media_from_discord_payload

    url = primary_media_from_discord_payload(
        {
            "content": "",
            "attachments": [
                {
                    "content_type": "image/png",
                    "filename": "a.png",
                    "url": "https://cdn.discordapp.com/attachments/1/2/a.png",
                    "proxy_url": "https://media.discordapp.net/attachments/1/2/a.png",
                }
            ],
            "embeds": [],
        }
    )
    assert url == "https://media.discordapp.net/attachments/1/2/a.png"


def test_primary_media_from_klipy_gifv_uses_thumbnail() -> None:
    from app.services.feed_rebuild import primary_media_from_discord_payload

    url = primary_media_from_discord_payload(
        {
            "content": "https://klipy.com/gifs/cute-15",
            "attachments": [],
            "embeds": [
                {
                    "type": "gifv",
                    "url": "https://klipy.com/gifs/cute-15",
                    "thumbnail": {
                        "url": "https://static.klipy.com/ii/abc/thumb.webp",
                    },
                    "video": {
                        "url": "https://static.klipy.com/ii/abc/clip.mp4",
                    },
                }
            ],
        }
    )
    assert url == "https://static.klipy.com/ii/abc/thumb.webp"


def test_build_feed_embed_strips_klipy_page_link() -> None:
    thumb = "https://static.klipy.com/ii/abc/thumb.webp"
    page = "https://klipy.com/gifs/cute-15"
    msg = _msg("klipy", media=thumb, excerpt=page)
    payload = build_feed_embed(
        rank=1,
        message=msg,  # type: ignore[arg-type]
        upvote_emoji="👍",
        downvote_emoji="👎",
    )
    embed = payload["embeds"][0]
    assert embed["image"]["url"] == thumb
    assert page not in embed["description"]
    assert "klipy.com/gifs" not in embed["description"]



def test_build_feed_embed_trending_titles() -> None:
    for rank in (1, 2, 25):
        payload = build_feed_embed(
            rank=rank,
            message=_msg(str(rank)),  # type: ignore[arg-type]
            upvote_emoji="👍",
            downvote_emoji="👎",
            window="weekly",
        )
        assert payload["embeds"][0]["title"] == f"#{rank} Trending"
        assert "Net" not in payload["embeds"][0]["title"]
        assert "Weekly" in payload["embeds"][0]["footer"]["text"]


def test_build_feed_embed_truncates_long_body() -> None:
    long = "x" * 5000
    payload = build_feed_embed(
        rank=3,
        message=_msg("long", excerpt=long),  # type: ignore[arg-type]
        upvote_emoji="👍",
        downvote_emoji="👎",
    )
    desc = payload["embeds"][0]["description"]
    assert len(desc) < 4096
    assert "View Original Message" in desc
    assert "…" in desc


def test_build_feed_embed_never_empty_placeholder() -> None:
    msg = _msg("1", net=2, excerpt="", author_display_name=None, author_avatar_url=None)
    payload = build_feed_embed(
        rank=2,
        message=msg,  # type: ignore[arg-type]
        upvote_emoji="👍",
        downvote_emoji="👎",
    )
    assert payload["embeds"][0]["title"] == "#2 Trending"
    assert "empty slot" not in payload["embeds"][0]["title"].lower()
    assert any(f["name"] == "Author" for f in payload["embeds"][0]["fields"])


def test_needs_full_rebuild_on_order_change() -> None:
    top = [_msg("A", net=100), _msg("B", net=50)]
    # Entries ranked #1→#N ascending matches desired send order
    existing = [
        SimpleNamespace(
            source_message_id="A",
            feed_channel_id="ch",
            rank=1,
        ),
        SimpleNamespace(
            source_message_id="B",
            feed_channel_id="ch",
            rank=2,
        ),
    ]
    assert needs_full_rebuild(existing, top, "ch") is False  # type: ignore[arg-type]

    existing_wrong = [
        SimpleNamespace(source_message_id="B", feed_channel_id="ch", rank=1),
        SimpleNamespace(source_message_id="A", feed_channel_id="ch", rank=2),
    ]
    assert needs_full_rebuild(existing_wrong, top, "ch") is True  # type: ignore[arg-type]


def test_needs_full_rebuild_when_fewer_slots() -> None:
    top = [_msg("A", net=10)]
    existing = [
        SimpleNamespace(source_message_id="A", feed_channel_id="ch", rank=1),
        SimpleNamespace(source_message_id=None, feed_channel_id="ch", rank=2),
    ]
    assert needs_full_rebuild(existing, top, "ch") is True  # type: ignore[arg-type]


def test_feed_channel_permission_overwrites_deny_send() -> None:
    from app.integrations.discord.bot_rest import (
        FEED_EVERYONE_DENY,
        PERM_SEND_MESSAGES,
        feed_channel_permission_overwrites,
    )

    overs = feed_channel_permission_overwrites("guild1", bot_user_id="bot1")
    everyone = overs[0]
    assert everyone["id"] == "guild1"
    assert everyone["type"] == 0
    deny = int(everyone["deny"])
    assert deny & PERM_SEND_MESSAGES
    assert deny == FEED_EVERYONE_DENY
    bot = overs[1]
    assert bot["id"] == "bot1"
    assert bot["type"] == 1
    assert int(bot["allow"]) > 0
