"""Unit tests for campaign Postgres mapping and dual-write store helpers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.repositories.campaign_repository import (
    campaign_dict_to_columns,
    row_to_campaign_dict,
)
from app.services import campaign_store as store


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.lists: dict[str, list[str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool | None = None,
        ex: int | None = None,
    ) -> bool | None:
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def delete(self, key: str) -> int:
        return 1 if self.kv.pop(key, None) is not None else 0

    async def sadd(self, key: str, *members: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(str(m) for m in members)
        return len(bucket) - before

    async def srem(self, key: str, *members: str) -> int:
        bucket = self.sets.setdefault(key, set())
        removed = 0
        for member in members:
            if str(member) in bucket:
                bucket.remove(str(member))
                removed += 1
        return removed

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def lpush(self, key: str, value: str) -> int:
        bucket = self.lists.setdefault(key, [])
        bucket.insert(0, value)
        return len(bucket)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        bucket = self.lists.setdefault(key, [])
        # Redis end is inclusive.
        self.lists[key] = bucket[start : end + 1]

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        bucket = self.zsets.setdefault(key, {})
        bucket.update(mapping)
        return len(mapping)

    async def zrem(self, key: str, *members: str) -> int:
        bucket = self.zsets.setdefault(key, {})
        removed = 0
        for member in members:
            if member in bucket:
                del bucket[member]
                removed += 1
        return removed

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        bucket = self.lists.get(key, [])
        if end < 0:
            end = len(bucket) - 1
        return bucket[start : end + 1]


def test_campaign_dict_round_trip_preserves_runtime_fields() -> None:
    campaign_id = str(uuid4())
    original: dict[str, Any] = {
        "id": campaign_id,
        "guild_id": "123456789012345678",
        "title": "Launch Drop",
        "status": "queued",
        "message": "Hello",
        "sent_count": 3,
        "failed_count": 1,
        "delivery_target": "dm",
        "audience": {"type": "all"},
        "platform_messages": {"discord": "hi"},
        "launch_at": "2026-08-10T12:00:00+00:00",
        "created_by": "987654321098765432",
    }

    columns = campaign_dict_to_columns(original)
    assert columns["name"] == "Launch Drop"
    assert columns["status"] == "queued"
    assert columns["raw_payload"]["sent_count"] == 3
    assert columns["raw_payload"]["message"] == "Hello"

    class _Row:
        id = columns["id"]
        guild_id = columns["guild_id"]
        name = columns["name"]
        status = columns["status"]
        platform_messages = columns["platform_messages"]
        audience = columns["audience"]
        raw_payload = columns["raw_payload"]
        created_by = columns["created_by"]
        launch_at = columns["launch_at"]
        next_run_at = None
        created_at = None
        updated_at = None

    rebuilt = row_to_campaign_dict(_Row())  # type: ignore[arg-type]
    assert rebuilt["id"] == campaign_id
    assert rebuilt["title"] == "Launch Drop"
    assert rebuilt["sent_count"] == 3
    assert rebuilt["message"] == "Hello"
    assert rebuilt["delivery_target"] == "dm"


@pytest.mark.anyio
async def test_save_get_survives_redis_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = str(uuid4())
    campaign = {
        "id": campaign_id,
        "guild_id": "123456789012345678",
        "title": "Durable",
        "status": "draft",
        "sent_count": 0,
    }
    pg: dict[str, dict[str, Any]] = {}

    async def _upsert(payload: dict[str, Any]) -> None:
        pg[payload["id"]] = dict(payload)

    async def _get(cid: str) -> dict[str, Any] | None:
        return pg.get(cid)

    async def _list() -> list[dict[str, Any]]:
        return list(pg.values())

    async def _delete(cid: str) -> None:
        pg.pop(cid, None)

    async def _activity(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(store, "CAMPAIGN_PG_ENABLED", True)
    monkeypatch.setattr(store, "_pg_upsert", _upsert)
    monkeypatch.setattr(store, "_pg_get", _get)
    monkeypatch.setattr(store, "_pg_list", _list)
    monkeypatch.setattr(store, "_pg_delete", _delete)
    monkeypatch.setattr(store, "_pg_add_activity", _activity)

    redis = FakeRedis()
    await store.save_campaign(redis, campaign)

    # Simulate Redis flush.
    redis.kv.clear()
    redis.sets.clear()

    loaded = await store.get_campaign(redis, campaign_id)
    assert loaded is not None
    assert loaded["title"] == "Durable"
    assert campaign_id in redis.kv[store.campaign_key(campaign_id)] or redis.kv


@pytest.mark.anyio
async def test_list_rehydrates_from_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = str(uuid4())
    durable = {
        "id": campaign_id,
        "guild_id": "123456789012345678",
        "title": "From PG",
        "status": "draft",
        "updated_at": "2026-08-10T00:00:00+00:00",
    }

    async def _list() -> list[dict[str, Any]]:
        return [durable]

    async def _noop_upsert(_payload: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(store, "CAMPAIGN_PG_ENABLED", True)
    monkeypatch.setattr(store, "_pg_list", _list)
    monkeypatch.setattr(store, "_pg_upsert", _noop_upsert)
    monkeypatch.setattr(store, "_pg_get", lambda _cid: None)

    redis = FakeRedis()
    listed = await store.list_campaigns(redis)
    assert len(listed) == 1
    assert listed[0]["title"] == "From PG"
    assert campaign_id in redis.sets[store.CAMPAIGNS_KEY]


@pytest.mark.anyio
async def test_list_activity_falls_back_to_redis_when_pg_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _pg_activity(
        *,
        campaign_id: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        _ = campaign_id
        _ = limit
        return []

    monkeypatch.setattr(store, "_pg_list_activity", _pg_activity)
    redis = FakeRedis()
    await redis.lpush(
        store.ACTIVITY_KEY,
        '{"campaign_id":"c1","type":"queued","created_at":"2026-01-01T00:00:00+00:00"}',
    )
    items = await store.list_activity(redis, limit=30)
    assert len(items) == 1
    assert items[0]["campaign_id"] == "c1"


@pytest.mark.anyio
async def test_unsubscribed_uses_pg_and_rehydrates_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _pg_unsubscribed(*, guild_id: str) -> list[str]:
        assert guild_id == "123"
        return ["9", "8"]

    monkeypatch.setattr(store, "_pg_list_unsubscribed_user_ids", _pg_unsubscribed)
    redis = FakeRedis()
    user_ids = await store.list_unsubscribed_user_ids(redis, guild_id="123")
    assert user_ids == ["8", "9"]
    assert redis.sets["norgoth:guild:123:campaigns:unsubscribed"] == {"8", "9"}


@pytest.mark.anyio
async def test_list_campaigns_by_statuses_rehydrates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable = [
        {
            "id": str(uuid4()),
            "guild_id": "123456789012345678",
            "title": "Queued",
            "status": "queued",
        }
    ]

    async def _pg_statuses(statuses: list[str]) -> list[dict[str, Any]]:
        assert statuses == ["queued"]
        return durable

    monkeypatch.setattr(store, "_pg_list_by_statuses", _pg_statuses)
    redis = FakeRedis()
    rows = await store.list_campaigns_by_statuses(redis, ["queued"])
    assert rows[0]["status"] == "queued"
    assert durable[0]["id"] in redis.sets[store.CAMPAIGNS_KEY]


@pytest.mark.anyio
async def test_mark_unsubscribed_dual_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    async def _pg_upsert(*, guild_id: str, user_id: str) -> None:
        calls.append((guild_id, user_id))

    monkeypatch.setattr(store, "_pg_upsert_unsubscribe", _pg_upsert)
    redis = FakeRedis()
    await store.mark_unsubscribed(redis, guild_id="123", user_id="456")
    assert calls == [("123", "456")]
    assert redis.sets["norgoth:guild:123:campaigns:unsubscribed"] == {"456"}
