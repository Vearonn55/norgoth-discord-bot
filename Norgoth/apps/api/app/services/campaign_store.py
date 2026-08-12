from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.db.session import get_session_factory
from app.repositories.campaign_repository import (
    CampaignRepository,
    row_to_campaign_dict,
)

logger = logging.getLogger("norgoth.campaign_store")

def _redis_url() -> str:
    return os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0")


def _campaign_pg_enabled() -> bool:
    # Read at call-time so Docker/env_file values are visible even if this
    # module was imported before a late load_dotenv() in workers.
    return os.getenv("NORGOTH_CAMPAIGN_PG_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# Back-compat for tests that monkeypatch the module attribute.
CAMPAIGN_PG_ENABLED = _campaign_pg_enabled()
REDIS_URL = _redis_url()

CAMPAIGNS_KEY = "norgoth:campaigns"
CAMPAIGN_KEY_PREFIX = "norgoth:campaign:"
ACTIVITY_KEY = "norgoth:campaign_activity"
EXECUTION_QUEUE_KEY = "norgoth:campaign_execution_queue"
SCHEDULED_ZSET_KEY = "norgoth:campaign_scheduled"
CLAIMED_KEY_PREFIX = "norgoth:campaign_claimed:"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def campaign_key(campaign_id: str) -> str:
    return f"{CAMPAIGN_KEY_PREFIX}{campaign_id}"


def claimed_key(campaign_id: str) -> str:
    return f"{CLAIMED_KEY_PREFIX}{campaign_id}"


async def get_redis() -> redis.Redis:
    # Prefer live env (Compose); fall back to module attr for tests/monkeypatch.
    return redis.from_url(
        os.getenv("NORGOTH_REDIS_URL") or REDIS_URL,
        decode_responses=True,
    )


async def serialize_campaign(campaign: Dict[str, Any]) -> str:
    return json.dumps(campaign, ensure_ascii=False)


async def deserialize_campaign(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None

    return json.loads(raw)


async def _pg_upsert(campaign: Dict[str, Any]) -> None:
    if not CAMPAIGN_PG_ENABLED:
        return
    if not campaign.get("guild_id"):
        raise ValueError(
            f"Campaign {campaign.get('id')} missing guild_id; refusing Redis-only write."
        )

    factory = get_session_factory()
    async with factory() as session:
        await CampaignRepository(session).upsert(campaign)


async def _pg_get(campaign_id: str) -> Optional[Dict[str, Any]]:
    if not CAMPAIGN_PG_ENABLED:
        return None

    factory = get_session_factory()
    async with factory() as session:
        row = await CampaignRepository(session).get(campaign_id)
        if row is None:
            return None
        return row_to_campaign_dict(row)


async def _pg_list() -> List[Dict[str, Any]]:
    if not CAMPAIGN_PG_ENABLED:
        return []

    factory = get_session_factory()
    async with factory() as session:
        rows = await CampaignRepository(session).list_all()
        return [row_to_campaign_dict(row) for row in rows]


async def _pg_delete(campaign_id: str) -> None:
    if not CAMPAIGN_PG_ENABLED:
        return

    factory = get_session_factory()
    async with factory() as session:
        await CampaignRepository(session).delete(campaign_id)


async def _pg_add_activity(
    campaign_id: str,
    kind: str,
    payload: Dict[str, Any],
) -> None:
    if not CAMPAIGN_PG_ENABLED:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            await CampaignRepository(session).add_activity(campaign_id, kind, payload)
    except Exception:  # noqa: BLE001 — activity durability must not break Redis path
        logger.exception("Failed to persist campaign activity to Postgres")


async def _pg_list_activity(
    *,
    campaign_id: str | None = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    if not CAMPAIGN_PG_ENABLED:
        return []
    factory = get_session_factory()
    async with factory() as session:
        rows = await CampaignRepository(session).list_activity(
            campaign_id=campaign_id, limit=limit
        )
        activities: List[Dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload) if isinstance(row.payload, dict) else {}
            payload.setdefault("id", str(row.id))
            payload.setdefault("campaign_id", str(row.campaign_id))
            payload.setdefault("type", row.kind)
            payload.setdefault("created_at", row.created_at.isoformat())
            activities.append(payload)
        return activities


async def _pg_upsert_unsubscribe(*, guild_id: str, user_id: str) -> None:
    if not CAMPAIGN_PG_ENABLED:
        return
    factory = get_session_factory()
    async with factory() as session:
        await CampaignRepository(session).upsert_unsubscribe(
            guild_id=guild_id, user_id=user_id
        )


async def _pg_list_unsubscribed_user_ids(*, guild_id: str) -> List[str]:
    if not CAMPAIGN_PG_ENABLED:
        return []
    factory = get_session_factory()
    async with factory() as session:
        return await CampaignRepository(session).list_unsubscribed_user_ids(
            guild_id=guild_id
        )


async def _pg_list_by_statuses(statuses: List[str]) -> List[Dict[str, Any]]:
    if not CAMPAIGN_PG_ENABLED:
        return []
    factory = get_session_factory()
    async with factory() as session:
        rows = await CampaignRepository(session).list_by_statuses(statuses)
        # Convert while the session is open — closed/detached rows raise
        # DetachedInstanceError / MissingGreenlet and crash the worker.
        return [row_to_campaign_dict(row) for row in rows]


async def add_activity(
    redis_client: redis.Redis,
    campaign: Dict[str, Any],
    activity_type: str,
    message: str,
) -> Dict[str, Any]:
    activity = {
        "id": str(uuid.uuid4()),
        "campaign_id": campaign["id"],
        "campaign_title": campaign.get("title") or campaign.get("name") or "Untitled Campaign",
        "type": activity_type,
        "message": message,
        "sent_count": int(campaign.get("sent_count") or 0),
        "failed_count": int(campaign.get("failed_count") or 0),
        "audience_count": int(campaign.get("audience_count") or 0),
        "created_at": now_iso(),
    }

    await redis_client.lpush(ACTIVITY_KEY, json.dumps(activity, ensure_ascii=False))
    await redis_client.ltrim(ACTIVITY_KEY, 0, 99)
    await _pg_add_activity(str(campaign["id"]), activity_type, activity)

    return activity


async def list_activity(
    redis_client: redis.Redis,
    *,
    campaign_id: str | None = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    # Postgres is the durable source for historical activity.
    from_pg = await _pg_list_activity(campaign_id=campaign_id, limit=limit)
    if from_pg:
        return from_pg

    raw_items = await redis_client.lrange(ACTIVITY_KEY, 0, max(limit - 1, 0))
    items = [json.loads(item) for item in raw_items]
    if campaign_id:
        items = [item for item in items if item.get("campaign_id") == campaign_id]
    return items[:limit]


async def save_campaign(
    redis_client: redis.Redis,
    campaign: Dict[str, Any],
) -> Dict[str, Any]:
    campaign["updated_at"] = now_iso()

    # Postgres first when enabled so Redis flush cannot lose the write.
    await _pg_upsert(campaign)

    await redis_client.set(campaign_key(campaign["id"]), await serialize_campaign(campaign))
    await redis_client.sadd(CAMPAIGNS_KEY, campaign["id"])

    return campaign


async def get_campaign(
    redis_client: redis.Redis,
    campaign_id: str,
) -> Optional[Dict[str, Any]]:
    # Prefer durable source when enabled; Redis is cache.
    from_pg = await _pg_get(campaign_id)
    if from_pg is not None:
        await redis_client.set(
            campaign_key(campaign_id),
            await serialize_campaign(from_pg),
        )
        await redis_client.sadd(CAMPAIGNS_KEY, campaign_id)
        return from_pg

    raw = await redis_client.get(campaign_key(campaign_id))
    cached = await deserialize_campaign(raw)
    if cached:
        return cached

    return None


async def list_campaigns(redis_client: redis.Redis) -> List[Dict[str, Any]]:
    # Postgres authoritative listing.
    from_pg = await _pg_list()
    if from_pg:
        for campaign in from_pg:
            await redis_client.set(
                campaign_key(campaign["id"]),
                await serialize_campaign(campaign),
            )
            await redis_client.sadd(CAMPAIGNS_KEY, campaign["id"])
        from_pg.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return from_pg

    # Emergency Redis-only mode or PG unavailable.
    campaign_ids = await redis_client.smembers(CAMPAIGNS_KEY)
    campaigns: List[Dict[str, Any]] = []
    for campaign_id in campaign_ids:
        raw = await redis_client.get(campaign_key(campaign_id))
        cached = await deserialize_campaign(raw)
        if cached:
            campaigns.append(cached)
    campaigns.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return campaigns


async def delete_campaign(redis_client: redis.Redis, campaign_id: str) -> None:
    await _pg_delete(campaign_id)
    await redis_client.delete(campaign_key(campaign_id))
    await redis_client.srem(CAMPAIGNS_KEY, campaign_id)
    await redis_client.zrem(SCHEDULED_ZSET_KEY, campaign_id)


async def enqueue_campaign(redis_client: redis.Redis, campaign_id: str) -> None:
    await redis_client.lpush(EXECUTION_QUEUE_KEY, campaign_id)


async def schedule_campaign(
    redis_client: redis.Redis,
    campaign: Dict[str, Any],
) -> bool:
    launch_at = campaign.get("launch_at")
    launch_time = parse_datetime(launch_at)

    if not launch_time:
        return False

    score = launch_time.timestamp()
    await redis_client.zadd(SCHEDULED_ZSET_KEY, {campaign["id"]: score})

    return True


async def unschedule_campaign(redis_client: redis.Redis, campaign_id: str) -> None:
    await redis_client.zrem(SCHEDULED_ZSET_KEY, campaign_id)


async def get_due_scheduled_campaign_ids(redis_client: redis.Redis) -> List[str]:
    now_score = datetime.now(timezone.utc).timestamp()

    campaign_ids = await redis_client.zrangebyscore(
        SCHEDULED_ZSET_KEY,
        min="-inf",
        max=now_score,
    )

    return list(campaign_ids)


async def pop_execution_campaign_id(redis_client: redis.Redis) -> Optional[str]:
    campaign_id = await redis_client.rpop(EXECUTION_QUEUE_KEY)

    if not campaign_id:
        return None

    return campaign_id


async def mark_unsubscribed(
    redis_client: redis.Redis,
    *,
    guild_id: str,
    user_id: str,
) -> None:
    await _pg_upsert_unsubscribe(guild_id=guild_id, user_id=user_id)
    await redis_client.sadd(f"norgoth:guild:{guild_id}:campaigns:unsubscribed", user_id)


async def list_unsubscribed_user_ids(
    redis_client: redis.Redis,
    *,
    guild_id: str,
) -> List[str]:
    from_pg = await _pg_list_unsubscribed_user_ids(guild_id=guild_id)
    if from_pg:
        key = f"norgoth:guild:{guild_id}:campaigns:unsubscribed"
        await redis_client.delete(key)
        if from_pg:
            await redis_client.sadd(key, *from_pg)
        return sorted(from_pg)

    raw_members = await redis_client.smembers(
        f"norgoth:guild:{guild_id}:campaigns:unsubscribed"
    )
    return sorted(
        item.decode("utf-8") if isinstance(item, bytes) else str(item)
        for item in raw_members
    )


async def list_campaigns_by_statuses(
    redis_client: redis.Redis,
    statuses: List[str],
) -> List[Dict[str, Any]]:
    campaigns = await _pg_list_by_statuses(statuses)
    if not campaigns:
        fallback = await list_campaigns(redis_client)
        campaigns = [c for c in fallback if str(c.get("status")) in statuses]
    for campaign in campaigns:
        await redis_client.set(
            campaign_key(campaign["id"]),
            await serialize_campaign(campaign),
        )
        await redis_client.sadd(CAMPAIGNS_KEY, campaign["id"])
    return campaigns


async def claim_campaign_for_execution(
    redis_client: redis.Redis,
    campaign_id: str,
    *,
    ttl_seconds: int = 300,
) -> bool:
    result = await redis_client.set(claimed_key(campaign_id), now_iso(), nx=True, ex=ttl_seconds)
    return bool(result)


async def release_campaign_claim(redis_client: redis.Redis, campaign_id: str) -> None:
    await redis_client.delete(claimed_key(campaign_id))
