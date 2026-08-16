"""Unit tests for clean-room Link Embeds URL transforms."""

from __future__ import annotations

from bot.rich_link_embeds_transform import (
    ALLOWED_REWRITE_HOSTS,
    extract_urls,
    rewrite_url,
    transform_message_urls,
)

ENABLED = {
    "twitter": True,
    "bluesky": True,
    "tiktok": True,
    "reddit": True,
    "instagram": True,
    "pixiv": True,
    "youtube_shorts": True,
}

HOSTS = dict(ALLOWED_REWRITE_HOSTS)


def test_twitter_status_strips_query() -> None:
    out = rewrite_url(
        "https://x.com/user/status/123?s=20&t=abc",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://fxtwitter.com/user/status/123"


def test_bluesky_post() -> None:
    out = rewrite_url(
        "https://bsky.app/profile/alice.bsky.social/post/abc123",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://bskx.app/profile/alice.bsky.social/post/abc123"


def test_tiktok_video() -> None:
    out = rewrite_url(
        "https://www.tiktok.com/@creator/video/9876543210",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://vxtiktok.com/@creator/video/9876543210"


def test_instagram_reel() -> None:
    out = rewrite_url(
        "https://www.instagram.com/reel/AbCdEf123/",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://instagram7.com/reel/AbCdEf123/"


def test_instagram_profile_skipped() -> None:
    assert (
        rewrite_url(
            "https://www.instagram.com/someuser/",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_reddit_and_short() -> None:
    assert (
        rewrite_url(
            "https://www.reddit.com/r/python/comments/abc/title/",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        == "https://vxreddit.com/r/python/comments/abc/title/"
    )
    assert (
        rewrite_url(
            "https://redd.it/abc123",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        == "https://vxreddit.com/abc123"
    )


def test_reddit_share_shortcut_skipped() -> None:
    assert (
        rewrite_url(
            "https://www.reddit.com/r/python/s/AbCdEf",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_pixiv_artwork() -> None:
    out = rewrite_url(
        "https://www.pixiv.net/artworks/12345678",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://phixiv.net/artworks/12345678"


def test_pixiv_legacy_illust() -> None:
    out = rewrite_url(
        "https://www.pixiv.net/member_illust.php?illust_id=12345678&mode=medium",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://phixiv.net/artworks/12345678"


def test_youtube_shorts_to_youtu_be() -> None:
    out = rewrite_url(
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
    )
    assert out == "https://youtu.be/dQw4w9WgXcQ"


def test_youtube_watch_unchanged() -> None:
    assert (
        rewrite_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_new_platforms_default_off_when_missing() -> None:
    platforms = {
        "twitter": True,
        "bluesky": True,
        "tiktok": True,
        "reddit": True,
    }
    assert (
        rewrite_url(
            "https://www.instagram.com/p/AbCd/",
            enabled_platforms=platforms,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_disabled_platform_skipped() -> None:
    platforms = {**ENABLED, "twitter": False}
    assert (
        rewrite_url(
            "https://twitter.com/user/status/1",
            enabled_platforms=platforms,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_unsupported_domain() -> None:
    assert (
        rewrite_url(
            "https://example.com/post/1",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_lookalike_host_rejected() -> None:
    assert (
        rewrite_url(
            "https://twitter.com.evil.example/user/status/1",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )
    assert (
        rewrite_url(
            "https://nottwitter.com/user/status/1",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_credentials_in_url_rejected() -> None:
    assert (
        rewrite_url(
            "https://user:pass@x.com/user/status/1",
            enabled_platforms=ENABLED,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_instagram_disabled_skips() -> None:
    platforms = {**ENABLED, "instagram": False}
    assert (
        rewrite_url(
            "https://www.instagram.com/reel/AbCdEf123/",
            enabled_platforms=platforms,
            rewrite_hosts=HOSTS,
        )
        is None
    )


def test_allowlist_has_no_ddinstagram() -> None:
    assert "ddinstagram" not in str(ALLOWED_REWRITE_HOSTS)
    assert ALLOWED_REWRITE_HOSTS["instagram"] == "instagram7.com"


def test_unapproved_rewrite_host_ignored() -> None:
    out = rewrite_url(
        "https://x.com/user/status/1",
        enabled_platforms=ENABLED,
        rewrite_hosts={**HOSTS, "twitter": "evil.example"},
    )
    assert out == "https://fxtwitter.com/user/status/1"


def test_code_blocks_ignored() -> None:
    content = (
        "see https://x.com/u/status/1 and "
        "```\nhttps://x.com/u/status/2\n``` "
        "also `https://x.com/u/status/3`"
    )
    urls = extract_urls(content)
    assert urls == ["https://x.com/u/status/1"]


def test_angle_bracket_url() -> None:
    urls = extract_urls("check <https://x.com/u/status/9>")
    assert urls == ["https://x.com/u/status/9"]


def test_multiple_links_capped() -> None:
    content = (
        "https://x.com/a/status/1 "
        "https://bsky.app/profile/a/post/b "
        "https://www.reddit.com/r/x/comments/y/z/ "
        "https://www.tiktok.com/@c/video/9"
    )
    out = transform_message_urls(
        content,
        enabled_platforms=ENABLED,
        rewrite_hosts=HOSTS,
        max_links=2,
    )
    assert len(out) == 2
    assert out[0].startswith("https://fxtwitter.com/")
    assert out[1].startswith("https://bskx.app/")
