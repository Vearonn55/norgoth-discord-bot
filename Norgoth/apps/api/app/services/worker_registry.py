"""Canonical NorBot worker registry for heartbeats and health aggregation.

Every deployed background process that publishes a Redis heartbeat must appear
here. Worker Health and tests consume this list so new workers cannot be
silently omitted from the operational view.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from redis.asyncio import Redis

WorkerState = Literal["online", "offline", "unknown", "degraded", "paused"]
HeartbeatValueKind = Literal["iso", "presence"]

DEFAULT_HEARTBEAT_TTL_SECONDS = 45

# Stable Redis keys — must match producers in workers / bot.
CAMPAIGN_HEARTBEAT_KEY = "norgoth:worker:heartbeat"
CONTENT_NOTIFICATIONS_HEARTBEAT_KEY = "norgoth:content_notifications:worker:heartbeat"
RSS_HEARTBEAT_KEY = "norgoth:rss:worker:heartbeat"
BOT_HEARTBEAT_KEY = "norgoth:bot:heartbeat"
BOT_STATUS_KEY = "norgoth:bot:status"
CAMPAIGN_QUEUE_STATE_KEY = "norgoth:campaign_queue_state"


@dataclass(frozen=True, slots=True)
class WorkerTypeDefinition:
    """Typed registry entry for one NorBot worker / runtime process."""

    type: str
    display_name: str
    heartbeat_key: str
    expected_replicas: int
    heartbeat_value_kind: HeartbeatValueKind
    compose_service: str
    required: bool = True


WORKER_REGISTRY: tuple[WorkerTypeDefinition, ...] = (
    WorkerTypeDefinition(
        type="campaign",
        display_name="Campaign Worker",
        heartbeat_key=CAMPAIGN_HEARTBEAT_KEY,
        expected_replicas=1,
        heartbeat_value_kind="iso",
        compose_service="campaign-worker",
    ),
    WorkerTypeDefinition(
        type="content_notifications",
        display_name="Content Notifications Worker",
        heartbeat_key=CONTENT_NOTIFICATIONS_HEARTBEAT_KEY,
        expected_replicas=1,
        heartbeat_value_kind="iso",
        compose_service="content-worker",
    ),
    WorkerTypeDefinition(
        type="rss_feeds",
        display_name="RSS Feeds Worker",
        heartbeat_key=RSS_HEARTBEAT_KEY,
        expected_replicas=1,
        heartbeat_value_kind="iso",
        compose_service="rss-worker",
    ),
    WorkerTypeDefinition(
        type="bot",
        display_name="Discord Bot",
        heartbeat_key=BOT_HEARTBEAT_KEY,
        expected_replicas=1,
        heartbeat_value_kind="iso",
        compose_service="bot",
    ),
)

WORKER_BY_TYPE: dict[str, WorkerTypeDefinition] = {
    entry.type: entry for entry in WORKER_REGISTRY
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_worker_definition(worker_type: str) -> WorkerTypeDefinition:
    try:
        return WORKER_BY_TYPE[worker_type]
    except KeyError as exc:
        raise KeyError(f"Unknown worker type: {worker_type}") from exc


async def publish_worker_heartbeat(
    redis_client: Redis,
    worker_type: str,
    *,
    ttl_seconds: int = DEFAULT_HEARTBEAT_TTL_SECONDS,
    at: datetime | None = None,
) -> str:
    """SET the registered heartbeat key with an ISO timestamp."""

    definition = get_worker_definition(worker_type)
    value = (at or datetime.now(timezone.utc)).isoformat()
    await redis_client.set(definition.heartbeat_key, value, ex=ttl_seconds)
    return value


def _decode(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return str(raw)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _heartbeat_age_seconds(
    last_heartbeat: str | None,
    *,
    now: datetime,
    value_kind: HeartbeatValueKind,
) -> int | None:
    if value_kind == "presence":
        return None
    parsed = _parse_iso(last_heartbeat)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


async def _bot_degraded(redis_client: Redis, *, heartbeat_present: bool) -> bool:
    if not heartbeat_present:
        return False
    raw = await redis_client.get(BOT_STATUS_KEY)
    decoded = _decode(raw)
    if not decoded:
        return True
    try:
        status = json.loads(decoded)
    except json.JSONDecodeError:
        return True
    if not isinstance(status, dict):
        return True
    return not bool(status.get("connected"))


async def _campaign_queue_paused(redis_client: Redis) -> bool:
    raw = await redis_client.get(CAMPAIGN_QUEUE_STATE_KEY)
    return _decode(raw) == "paused"


async def evaluate_worker_health(
    redis_client: Redis,
    definition: WorkerTypeDefinition,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate one worker type from Redis heartbeat (+ bot status)."""

    current = now or datetime.now(timezone.utc)
    try:
        raw = await redis_client.get(definition.heartbeat_key)
    except Exception:
        return {
            "type": definition.type,
            "display_name": definition.display_name,
            "compose_service": definition.compose_service,
            "state": "unknown",
            "online": False,
            "last_heartbeat": None,
            "heartbeat_age_seconds": None,
            "expected_instances": definition.expected_replicas,
            "observed_instances": 0,
            "required": definition.required,
        }

    last_heartbeat = _decode(raw)
    # Presence values like "1" are treated as online without a parseable time.
    if last_heartbeat == "1":
        last_heartbeat_display: str | None = None
        online = True
        age = None
    else:
        last_heartbeat_display = last_heartbeat
        online = bool(last_heartbeat)
        age = _heartbeat_age_seconds(
            last_heartbeat_display,
            now=current,
            value_kind=definition.heartbeat_value_kind,
        )

    state: WorkerState
    if not online:
        state = "offline"
    elif definition.type == "bot" and await _bot_degraded(
        redis_client, heartbeat_present=True
    ):
        state = "degraded"
    elif definition.type == "campaign" and await _campaign_queue_paused(redis_client):
        # Live worker with paused queue — not a crash.
        state = "paused"
    else:
        state = "online"

    return {
        "type": definition.type,
        "display_name": definition.display_name,
        "compose_service": definition.compose_service,
        "state": state,
        "online": state in ("online", "degraded", "paused"),
        "last_heartbeat": last_heartbeat_display if last_heartbeat != "1" else None,
        "heartbeat_age_seconds": age,
        "expected_instances": definition.expected_replicas,
        "observed_instances": 1 if online else 0,
        "required": definition.required,
    }


async def aggregate_workers_health(
    redis_client: Redis,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the Worker Health payload for every registered worker type."""

    current = now or datetime.now(timezone.utc)
    workers: list[dict[str, Any]] = []
    redis_ok = True
    try:
        await redis_client.ping()
    except Exception:
        redis_ok = False

    for definition in WORKER_REGISTRY:
        if not redis_ok:
            workers.append(
                {
                    "type": definition.type,
                    "display_name": definition.display_name,
                    "compose_service": definition.compose_service,
                    "state": "unknown",
                    "online": False,
                    "last_heartbeat": None,
                    "heartbeat_age_seconds": None,
                    "expected_instances": definition.expected_replicas,
                    "observed_instances": 0,
                    "required": definition.required,
                }
            )
            continue
        workers.append(
            await evaluate_worker_health(redis_client, definition, now=current)
        )

    if not redis_ok:
        overall: WorkerState = "unknown"
    else:
        states = {item["state"] for item in workers}
        if states <= {"online"}:
            overall = "online"
        elif states <= {"online", "paused"}:
            overall = "paused" if "paused" in states else "online"
        elif "offline" in states and states <= {"offline"}:
            overall = "offline"
        elif "unknown" in states and not (
            states & {"online", "degraded", "offline", "paused"}
        ):
            overall = "unknown"
        else:
            overall = "degraded"

    return {
        "workers": workers,
        "overall_state": overall,
        "redis_available": redis_ok,
        "checked_at": current.isoformat(),
    }
