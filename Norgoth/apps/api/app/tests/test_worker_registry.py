"""Unit tests for the canonical worker registry and health aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.services.worker_registry import (
    BOT_HEARTBEAT_KEY,
    BOT_STATUS_KEY,
    CAMPAIGN_HEARTBEAT_KEY,
    CAMPAIGN_QUEUE_STATE_KEY,
    CONTENT_NOTIFICATIONS_HEARTBEAT_KEY,
    RSS_HEARTBEAT_KEY,
    WORKER_REGISTRY,
    aggregate_workers_health,
    evaluate_worker_health,
    get_worker_definition,
    publish_worker_heartbeat,
)


EXPECTED_TYPES = {"campaign", "content_notifications", "rss_feeds", "bot"}
EXPECTED_KEYS = {
    CAMPAIGN_HEARTBEAT_KEY,
    CONTENT_NOTIFICATIONS_HEARTBEAT_KEY,
    RSS_HEARTBEAT_KEY,
    BOT_HEARTBEAT_KEY,
}


def test_registry_covers_deployed_workers() -> None:
    types = {entry.type for entry in WORKER_REGISTRY}
    keys = {entry.heartbeat_key for entry in WORKER_REGISTRY}
    assert types == EXPECTED_TYPES
    assert keys == EXPECTED_KEYS
    assert len(WORKER_REGISTRY) == 4


def test_registry_keys_match_known_producers() -> None:
    from app.services.content_notifications.queue import CONTENT_NOTIFICATION_HEARTBEAT
    from app.services.rss.coordinator import RSS_WORKER_HEARTBEAT
    from app.workers.campaign_worker import WORKER_HEARTBEAT_KEY

    assert CONTENT_NOTIFICATION_HEARTBEAT == CONTENT_NOTIFICATIONS_HEARTBEAT_KEY
    assert RSS_WORKER_HEARTBEAT == RSS_HEARTBEAT_KEY
    assert WORKER_HEARTBEAT_KEY == CAMPAIGN_HEARTBEAT_KEY
    assert get_worker_definition("bot").heartbeat_key == BOT_HEARTBEAT_KEY


@pytest.mark.anyio
async def test_publish_and_evaluate_online() -> None:
    store: dict[str, Any] = {}

    async def set_(key: str, value: str, ex: int | None = None) -> bool:
        store[key] = value
        return True

    async def get_(key: str) -> Any:
        return store.get(key)

    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=set_)
    redis.get = AsyncMock(side_effect=get_)
    redis.ping = AsyncMock(return_value=True)

    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    await publish_worker_heartbeat(redis, "campaign", at=now)
    result = await evaluate_worker_health(
        redis,
        get_worker_definition("campaign"),
        now=now,
    )
    assert result["state"] == "online"
    assert result["observed_instances"] == 1
    assert result["last_heartbeat"] == now.isoformat()


@pytest.mark.anyio
async def test_missing_heartbeat_is_offline() -> None:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    result = await evaluate_worker_health(redis, get_worker_definition("rss_feeds"))
    assert result["state"] == "offline"
    assert result["online"] is False
    assert result["observed_instances"] == 0


@pytest.mark.anyio
async def test_legacy_presence_heartbeat_still_online() -> None:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="1")
    result = await evaluate_worker_health(
        redis, get_worker_definition("content_notifications")
    )
    assert result["state"] == "online"
    assert result["last_heartbeat"] is None


@pytest.mark.anyio
async def test_bot_degraded_when_not_connected() -> None:
    store = {
        BOT_HEARTBEAT_KEY: datetime.now(timezone.utc).isoformat(),
        BOT_STATUS_KEY: '{"connected": false}',
    }
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda key: store.get(key))
    result = await evaluate_worker_health(redis, get_worker_definition("bot"))
    assert result["state"] == "degraded"
    assert result["online"] is True


@pytest.mark.anyio
async def test_aggregate_unknown_when_redis_down() -> None:
    redis = AsyncMock()
    redis.ping = AsyncMock(side_effect=ConnectionError("down"))
    payload = await aggregate_workers_health(redis)
    assert payload["redis_available"] is False
    assert payload["overall_state"] == "unknown"
    assert {w["type"] for w in payload["workers"]} == EXPECTED_TYPES
    assert all(w["state"] == "unknown" for w in payload["workers"])


@pytest.mark.anyio
async def test_campaign_paused_when_queue_paused() -> None:
    store = {
        CAMPAIGN_HEARTBEAT_KEY: datetime.now(timezone.utc).isoformat(),
        CAMPAIGN_QUEUE_STATE_KEY: "paused",
    }
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda key: store.get(key))
    result = await evaluate_worker_health(redis, get_worker_definition("campaign"))
    assert result["state"] == "paused"
    assert result["online"] is True


@pytest.mark.anyio
async def test_aggregate_lists_every_registered_worker() -> None:
    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc).isoformat()
    store = {
        CAMPAIGN_HEARTBEAT_KEY: now,
        CONTENT_NOTIFICATIONS_HEARTBEAT_KEY: now,
        RSS_HEARTBEAT_KEY: now,
        BOT_HEARTBEAT_KEY: now,
        BOT_STATUS_KEY: '{"connected": true}',
    }
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(side_effect=lambda key: store.get(key))
    payload = await aggregate_workers_health(redis)
    assert payload["overall_state"] == "online"
    assert len(payload["workers"]) == len(WORKER_REGISTRY)
