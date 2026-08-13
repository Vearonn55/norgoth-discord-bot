"""RSS quota helpers."""

from app.services.rss.quotas import (
    MAX_FEEDS_PER_GUILD,
    MIN_POLL_INTERVAL_SECONDS,
    clamp_poll_interval,
)


def test_clamp_poll_interval() -> None:
    assert clamp_poll_interval(60) == MIN_POLL_INTERVAL_SECONDS
    assert clamp_poll_interval(600) == 600
    assert clamp_poll_interval(None) == MIN_POLL_INTERVAL_SECONDS


def test_max_feeds_constant() -> None:
    assert MAX_FEEDS_PER_GUILD == 5
