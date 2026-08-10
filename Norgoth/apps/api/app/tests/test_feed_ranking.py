"""Unit tests for Feed Channels ranking helpers and config merge."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.feed_ranking import (
    DEFAULT_FEED_CONFIG,
    clamp_refresh_interval_minutes,
    composite_rank_score,
    compute_next_refresh_at,
    emoji_reaction_key,
    emojis_equal,
    feed_author_net_key,
    feed_dirty_key,
    feed_rank_key,
    merge_feed_config,
    touch_last_full_sync,
    window_bounds,
    windows_for_timestamp,
)


def test_merge_feed_config_defaults() -> None:
    merged = merge_feed_config(None)
    assert merged["enabled"] is False
    assert merged["min_net_score"] == 1
    assert merged["display_limit"] == 10
    assert merged["feed_category_id"] is None
    assert merged["last_full_sync_at"] is None
    assert merged["refresh_interval_minutes"] == 15
    assert set(merged["windows"]) == {"daily", "weekly", "monthly", "all_time"}
    for key in merged["windows"]:
        assert merged["windows"][key]["channel_id"] is None
        assert merged["windows"][key]["enabled"] is False


@pytest.mark.anyio
async def test_load_merged_feed_config_requires_redis_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: callers must not invoke read_through without redis."""

    from app.services import feed_ranking as ranking

    calls: list[tuple] = []

    class FakeRedis:
        async def get(self, key: str):
            return None

        async def set(self, key: str, value: str):
            return None

        async def aclose(self):
            return None

    async def fake_get_redis():
        return FakeRedis()

    async def fake_read_through(guild_id: str, feature_key: str, redis_client):
        calls.append((guild_id, feature_key, redis_client))
        return None

    monkeypatch.setattr(
        "app.services.campaign_store.get_redis", fake_get_redis
    )
    monkeypatch.setattr(
        "app.services.feature_config_store.read_through", fake_read_through
    )

    cfg = await ranking.load_merged_feed_config("123456789012345678")
    assert cfg["enabled"] is False
    assert len(calls) == 1
    assert calls[0][0] == "123456789012345678"
    assert calls[0][1] == "feed_channels"
    assert calls[0][2] is not None


def test_merge_feed_config_preserves_window_partials() -> None:
    merged = merge_feed_config(
        {
            "enabled": True,
            "min_net_score": 3,
            "windows": {
                "daily": {
                    "enabled": True,
                    "channel_id": "111111111111111111",
                }
            },
        }
    )
    assert merged["enabled"] is True
    assert merged["min_net_score"] == 3
    assert merged["windows"]["daily"]["channel_id"] == "111111111111111111"
    assert merged["windows"]["daily"]["enabled"] is True
    # Untouched windows keep defaults.
    assert merged["windows"]["weekly"]["channel_id"] is None
    assert merged["upvote_emoji"] == DEFAULT_FEED_CONFIG["upvote_emoji"]


def test_emoji_reaction_key_and_equality() -> None:
    up = {"kind": "unicode", "id": None, "name": "👍", "animated": False, "reaction": "👍"}
    down = {"kind": "unicode", "id": None, "name": "👎", "animated": False, "reaction": "👎"}
    custom = {
        "kind": "custom",
        "id": "222222222222222222",
        "name": "upvote",
        "animated": False,
        "reaction": "upvote:222222222222222222",
    }
    assert emoji_reaction_key(up) == "👍"
    assert emoji_reaction_key(custom) == "upvote:222222222222222222"
    assert emojis_equal(up, up) is True
    assert emojis_equal(up, down) is False
    assert emojis_equal(up, custom) is False


def test_window_bounds_utc_calendar() -> None:
    now = datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc)  # Monday

    daily_start, daily_end = window_bounds("daily", now=now)
    assert daily_start == datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
    assert daily_end == datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)

    weekly_start, weekly_end = window_bounds("weekly", now=now)
    assert weekly_start == datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
    assert weekly_end == datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc)

    monthly_start, monthly_end = window_bounds("monthly", now=now)
    assert monthly_start == datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    assert monthly_end == datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)

    all_start, all_end = window_bounds("all_time", now=now)
    assert all_start is None and all_end is None


def test_windows_for_timestamp_includes_matching() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    # Freeze "now" by using a message inside today.
    included = windows_for_timestamp(now)
    assert "all_time" in included
    assert "daily" in included
    assert "weekly" in included
    assert "monthly" in included

    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    old_windows = windows_for_timestamp(old)
    assert old_windows == ["all_time"]


def test_composite_rank_score_ordering() -> None:
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 2, 1, tzinfo=timezone.utc)
    assert composite_rank_score(5, 1, older) > composite_rank_score(4, 100, newer)
    assert composite_rank_score(5, 10, older) > composite_rank_score(5, 1, newer)
    assert composite_rank_score(5, 10, newer) > composite_rank_score(5, 10, older)


def test_redis_key_helpers() -> None:
    guild = "123456789012345678"
    assert feed_rank_key(guild, "daily") == f"norgoth:guild:{guild}:feed:rank:daily"
    assert feed_author_net_key(guild) == f"norgoth:guild:{guild}:feed:author:net"
    assert feed_dirty_key(guild) == f"norgoth:guild:{guild}:feed:dirty"


def test_feed_config_body_rejects_identical_emojis() -> None:
    from pydantic import ValidationError

    from app.routes.feed_channels import FeedConfigBody

    with pytest.raises(ValidationError):
        FeedConfigBody(
            enabled=True,
            upvote_emoji={
                "kind": "unicode",
                "name": "👍",
                "reaction": "👍",
            },
            downvote_emoji={
                "kind": "unicode",
                "name": "👍",
                "reaction": "👍",
            },
            source_channel_ids=["111111111111111111"],
        )


def test_adjust_counts_mutual_exclusivity() -> None:
    """Switching up→down adjusts counts without double-counting."""

    from app.services.feed_service import _adjust_counts

    class Msg:
        upvote_count = 1
        downvote_count = 0
        net_score = 1

    message = Msg()
    _adjust_counts(message, "up", "down")
    message.net_score = message.upvote_count - message.downvote_count
    assert message.upvote_count == 0
    assert message.downvote_count == 1
    assert message.net_score == -1

    _adjust_counts(message, "down", None)
    message.net_score = message.upvote_count - message.downvote_count
    assert message.upvote_count == 0
    assert message.downvote_count == 0
    assert message.net_score == 0

    _adjust_counts(message, None, "up")
    message.net_score = message.upvote_count - message.downvote_count
    assert message.upvote_count == 1
    assert message.net_score == 1


def test_compute_next_refresh_at_from_last_sync() -> None:
    last = "2026-08-10T12:00:00Z"
    now = datetime(2026, 8, 10, 12, 5, tzinfo=timezone.utc)
    next_at = compute_next_refresh_at(last, 15, now=now)
    assert next_at == "2026-08-10T12:15:00Z"


def test_compute_next_refresh_at_when_overdue_schedules_from_now() -> None:
    last = "2026-08-10T10:00:00Z"
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    next_at = compute_next_refresh_at(last, 15, now=now)
    assert next_at == "2026-08-10T12:15:00Z"


def test_compute_next_refresh_at_missing_last_uses_interval_from_now() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    next_at = compute_next_refresh_at(None, 20, now=now)
    assert next_at == "2026-08-10T12:20:00Z"


def test_touch_last_full_sync_and_merge_category() -> None:
    cfg = merge_feed_config(
        {
            "feed_category_id": "111",
            "refresh_interval_minutes": 30,
        }
    )
    assert cfg["feed_category_id"] == "111"
    assert clamp_refresh_interval_minutes(cfg["refresh_interval_minutes"]) == 30
    touch_last_full_sync(
        cfg, now=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    )
    assert cfg["last_full_sync_at"] == "2026-08-10T12:00:00Z"
    # Guild B merge is independent
    other = merge_feed_config({"feed_category_id": "222"})
    assert other["feed_category_id"] == "222"
    assert other["feed_category_id"] != cfg["feed_category_id"]
