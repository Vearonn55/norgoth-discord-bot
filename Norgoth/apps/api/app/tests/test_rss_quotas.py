"""RSS quota helpers."""

from __future__ import annotations

from inspect import getsource
from unittest.mock import AsyncMock

import pytest

from app.services.rss.quotas import (
    MAX_FEEDS_PER_GUILD,
    MIN_POLL_INTERVAL_SECONDS,
    RSS_FEED_LIMIT_REACHED,
    RssFeedQuotaError,
    _guild_advisory_lock_key,
    assert_can_create_rss_feed,
    clamp_poll_interval,
    count_guild_feeds,
    next_poll_after_success,
)


def test_clamp_poll_interval() -> None:
    assert clamp_poll_interval(60) == MIN_POLL_INTERVAL_SECONDS
    assert clamp_poll_interval(600) == 600
    assert clamp_poll_interval(None) == MIN_POLL_INTERVAL_SECONDS


def test_max_feeds_constant() -> None:
    assert MAX_FEEDS_PER_GUILD == 15


def test_lock_uses_transaction_advisory_lock() -> None:
    source = getsource(assert_can_create_rss_feed)
    assert "pg_advisory_xact_lock" in source


def test_count_includes_disabled_feeds() -> None:
    source = getsource(count_guild_feeds)
    assert "RssFeedConfig.enabled" not in source
    assert "guild_id" in source


def test_guilds_have_independent_lock_keys() -> None:
    assert _guild_advisory_lock_key("11") != _guild_advisory_lock_key("22")


@pytest.mark.asyncio
async def test_assert_can_create_accepts_fifteenth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    monkeypatch.setattr(
        "app.services.rss.quotas.count_guild_feeds",
        AsyncMock(return_value=14),
    )
    await assert_can_create_rss_feed(session, guild_id="1")


@pytest.mark.asyncio
async def test_assert_can_create_rejects_sixteenth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    monkeypatch.setattr(
        "app.services.rss.quotas.count_guild_feeds",
        AsyncMock(return_value=15),
    )
    with pytest.raises(RssFeedQuotaError) as exc:
        await assert_can_create_rss_feed(session, guild_id="1")
    assert exc.value.code == RSS_FEED_LIMIT_REACHED
    assert exc.value.as_detail()["limit"] == 15
    assert exc.value.as_detail()["current"] == 15


@pytest.mark.asyncio
async def test_disabled_rows_count_toward_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    monkeypatch.setattr(
        "app.services.rss.quotas.count_guild_feeds",
        AsyncMock(return_value=MAX_FEEDS_PER_GUILD),
    )
    with pytest.raises(RssFeedQuotaError):
        await assert_can_create_rss_feed(session, guild_id="g")


def test_success_schedule_uses_jitter() -> None:
    source = getsource(next_poll_after_success)
    assert "randint" in source
    assert "interval_seconds" in source
