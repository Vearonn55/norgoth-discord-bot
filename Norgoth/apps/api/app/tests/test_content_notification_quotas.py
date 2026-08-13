"""Unit tests for Content Notification per-platform quotas."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.content_notifications.quotas import (
    ACTIVE_LIMITS,
    CONTENT_NOTIFICATION_LIMIT_REACHED,
    ContentNotificationQuotaError,
    active_limit_for,
    assert_can_create,
    assert_can_enable,
    total_limit_for,
)


def test_active_limits_match_plan() -> None:
    assert ACTIVE_LIMITS == {
        "youtube": 10,
        "twitch": 10,
        "kick": 5,
        "x": 3,
        "tiktok": 0,
    }
    assert total_limit_for("youtube") == 30
    assert active_limit_for("tiktok") == 0


@pytest.mark.anyio
async def test_assert_can_create_rejects_at_active_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.quotas._lock_platform_subscriptions",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.content_notifications.quotas.platform_usage",
        AsyncMock(
            return_value={
                "platform": "x",
                "active_limit": 3,
                "active_count": 3,
                "active_remaining": 0,
                "total_limit": 9,
                "total_count": 3,
                "total_remaining": 6,
            }
        ),
    )
    with pytest.raises(ContentNotificationQuotaError) as exc:
        await assert_can_create(
            session, guild_id="1", platform="x", will_be_enabled=True
        )
    assert exc.value.code == CONTENT_NOTIFICATION_LIMIT_REACHED
    assert exc.value.as_detail()["limit"] == 3


@pytest.mark.anyio
async def test_assert_can_create_allows_disabled_when_active_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.quotas._lock_platform_subscriptions",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.content_notifications.quotas.platform_usage",
        AsyncMock(
            return_value={
                "platform": "kick",
                "active_limit": 5,
                "active_count": 5,
                "active_remaining": 0,
                "total_limit": 15,
                "total_count": 5,
                "total_remaining": 10,
            }
        ),
    )
    await assert_can_create(
        session, guild_id="1", platform="kick", will_be_enabled=False
    )


@pytest.mark.anyio
async def test_assert_can_enable_rejects_at_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.quotas._lock_platform_subscriptions",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.content_notifications.quotas.platform_usage",
        AsyncMock(
            return_value={
                "platform": "youtube",
                "active_limit": 10,
                "active_count": 10,
                "active_remaining": 0,
                "total_limit": 30,
                "total_count": 12,
                "total_remaining": 18,
            }
        ),
    )
    with pytest.raises(ContentNotificationQuotaError):
        await assert_can_enable(
            session,
            guild_id="1",
            platform="youtube",
            currently_enabled=False,
        )


@pytest.mark.anyio
async def test_assert_can_enable_noop_when_already_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    lock = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.quotas._lock_platform_subscriptions",
        lock,
    )
    await assert_can_enable(
        session,
        guild_id="1",
        platform="youtube",
        currently_enabled=True,
    )
    lock.assert_not_called()


@pytest.mark.anyio
async def test_concurrent_final_slot_second_request_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate two create attempts for the last active slot.

    The lock helper serializes callers; after the first succeeds, usage shows
    the platform at capacity so the second assert_can_create fails.
    """

    session = AsyncMock()
    lock = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.quotas._lock_platform_subscriptions",
        lock,
    )
    usage_calls = {"n": 0}

    async def usage(*_args, **_kwargs):
        usage_calls["n"] += 1
        # First caller sees room for one more; second sees full.
        if usage_calls["n"] == 1:
            return {
                "platform": "x",
                "active_limit": 3,
                "active_count": 2,
                "active_remaining": 1,
                "total_limit": 9,
                "total_count": 2,
                "total_remaining": 7,
            }
        return {
            "platform": "x",
            "active_limit": 3,
            "active_count": 3,
            "active_remaining": 0,
            "total_limit": 9,
            "total_count": 3,
            "total_remaining": 6,
        }

    monkeypatch.setattr(
        "app.services.content_notifications.quotas.platform_usage",
        usage,
    )
    await assert_can_create(
        session, guild_id="1", platform="x", will_be_enabled=True
    )
    with pytest.raises(ContentNotificationQuotaError) as exc:
        await assert_can_create(
            session, guild_id="1", platform="x", will_be_enabled=True
        )
    assert exc.value.code == CONTENT_NOTIFICATION_LIMIT_REACHED
    assert lock.await_count == 2
