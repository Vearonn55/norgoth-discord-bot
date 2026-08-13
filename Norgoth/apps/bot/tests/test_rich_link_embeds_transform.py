"""Unit tests for clean-room Rich Link Embeds URL transforms."""

from __future__ import annotations

from bot.rich_link_embeds_transform import (
    extract_urls,
    rewrite_url,
    transform_message_urls,
)

ENABLED = {
    "twitter": True,
    "bluesky": True,
    "tiktok": True,
    "reddit": True,
}

HOSTS = {
    "twitter": "fxtwitter.com",
    "bluesky": "bskx.app",
    "tiktok": "vxtiktok.com",
    "reddit": "vxreddit.com",
}


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


def test_code_blocks_ignored() -> None:
    content = (
        "see https://x.com/u/status/1 and "
        "```\nhttps://x.com/u/status/2\n``` "
        "also `https://x.com/u/status/3`"
    )
    urls = extract_urls(content)
    assert urls == ["https://x.com/u/status/1"]


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
