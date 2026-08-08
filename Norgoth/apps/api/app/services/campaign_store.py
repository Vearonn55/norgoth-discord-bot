from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

REDIS_URL = os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0")

CAMPAIGNS_KEY = "norgoth:campaigns"
CAMPAIGN_KEY_PREFIX = "norgoth:campaign:"
ACTIVITY_KEY = "norgoth:campaign_activity"
EXECUTION_QUEUE_KEY = "norgoth:campaign_execution_queue"
SCHEDULED_ZSET_KEY = "norgoth:campaign_scheduled"


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


async def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


async def serialize_campaign(campaign: Dict[str, Any]) -> str:
    return json.dumps(campaign, ensure_ascii=False)


async def deserialize_campaign(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None

    return json.loads(raw)


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

    return activity


async def save_campaign(
    redis_client: redis.Redis,
    campaign: Dict[str, Any],
) -> Dict[str, Any]:
    campaign["updated_at"] = now_iso()

    await redis_client.set(campaign_key(campaign["id"]), await serialize_campaign(campaign))
    await redis_client.sadd(CAMPAIGNS_KEY, campaign["id"])

    return campaign


async def get_campaign(
    redis_client: redis.Redis,
    campaign_id: str,
) -> Optional[Dict[str, Any]]:
    raw = await redis_client.get(campaign_key(campaign_id))
    return await deserialize_campaign(raw)


async def list_campaigns(redis_client: redis.Redis) -> List[Dict[str, Any]]:
    campaign_ids = await redis_client.smembers(CAMPAIGNS_KEY)

    campaigns: List[Dict[str, Any]] = []

    for campaign_id in campaign_ids:
        campaign = await get_campaign(redis_client, campaign_id)
        if campaign:
            campaigns.append(campaign)

    campaigns.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return campaigns


async def delete_campaign(redis_client: redis.Redis, campaign_id: str) -> None:
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


