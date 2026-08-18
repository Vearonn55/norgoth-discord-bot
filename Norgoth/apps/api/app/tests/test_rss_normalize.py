"""RSS URL normalization tests."""

from __future__ import annotations

from app.services.rss.normalize import canonical_feed_url
from app.services.rss.quotas import feed_url_hash


def test_canonical_feed_url_lowercases_host() -> None:
    url = canonical_feed_url("https://Example.COM/feed.xml")
    assert url == "https://example.com/feed.xml"


def test_feed_url_hash_ignores_case_and_trailing_slash_variants() -> None:
    a = feed_url_hash("https://example.com/feed")
    b = feed_url_hash("https://EXAMPLE.com/feed/")
    assert a == b
