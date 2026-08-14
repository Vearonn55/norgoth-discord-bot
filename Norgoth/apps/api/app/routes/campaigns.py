from __future__ import annotations

import uuid
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.dependencies import HTTPClientDependency
from app.api.v1.dependencies_auth import (
    OperatorSessionDependency,
    get_session_service,
    operator_manageable_guild_ids,
    require_guild_manager,
    require_operator_session,
    require_platform_admin,
)
from app.core.config import Settings, get_settings
from app.security.internal_auth import require_internal_token
from app.security.session import SessionService
from app.services.campaign_store import (
    add_activity,
    delete_campaign as store_delete_campaign,
    enqueue_campaign,
    get_campaign as store_get_campaign,
    get_redis,
    list_activity as store_list_activity,
    list_campaigns_by_statuses,
    list_campaigns as store_list_campaigns,
    list_unsubscribed_user_ids,
    mark_unsubscribed,
    now_iso,
    save_campaign,
    schedule_campaign,
    unschedule_campaign,
)

# Campaigns remain body-scoped to a guild. Router-level session auth is
# required; per-resource guild-manager checks run in each handler.
router = APIRouter(
    prefix="/campaigns",
    tags=["Campaigns"],
    dependencies=[Depends(require_operator_session)],
)
# Public (no session): deploy smoke + ops panels that only expose online/heartbeat.
public_router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
internal_router = APIRouter(prefix="/internal/campaigns", tags=["Internal Campaigns"])

from app.services.worker_registry import CAMPAIGN_HEARTBEAT_KEY

QUEUE_STATE_KEY = "norgoth:campaign_queue_state"

WORKER_HEARTBEAT_KEY = CAMPAIGN_HEARTBEAT_KEY

CampaignStatus = Literal[
    "draft",
    "scheduled",
    "queued",
    "running",
    "completed",
    "failed",
    "stopped",
]

DeliveryTarget = Literal["channel", "dm"]


class CampaignUpdate(BaseModel):
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    message: Optional[Any] = None
    body: Optional[Any] = None
    audience_count: Optional[int] = Field(default=None, ge=0)
    status: Optional[CampaignStatus] = None

    type: Optional[str] = None
    audience: Optional[Dict[str, Any]] = None
    platforms: Optional[list[str]] = None
    locales: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    risk_level: Optional[str] = None
    launch_at: Optional[str] = None
    discord_channel_id: Optional[str] = Field(default=None, pattern=r"^[0-9]{5,25}$")
    delivery_target: Optional[DeliveryTarget] = None
    guild_id: Optional[str] = Field(default=None, pattern=r"^[0-9]{5,25}$")
    dm_include_role_ids: Optional[list[str]] = None
    dm_exclude_role_ids: Optional[list[str]] = None


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_campaign(campaign: Dict[str, Any]) -> Dict[str, Any]:
    campaign["sent_count"] = safe_int(campaign.get("sent_count"))
    campaign["failed_count"] = safe_int(campaign.get("failed_count"))
    campaign["retry_count"] = safe_int(campaign.get("retry_count"))
    campaign["permanent_failed_count"] = safe_int(
        campaign.get("permanent_failed_count"),
    )
    return campaign


def extract_title(payload: Dict[str, Any]) -> str:
    title = payload.get("title") or payload.get("name")

    if isinstance(title, str) and title.strip():
        return title.strip()

    return "Untitled Campaign"


def extract_message(payload: Dict[str, Any]) -> str:
    message = payload.get("message")

    if isinstance(message, str):
        return message.strip()

    body = payload.get("body")

    if isinstance(body, str):
        return body.strip()

    if isinstance(body, dict):
        body_message = body.get("message")
        if isinstance(body_message, str):
            return body_message.strip()

        body_msg = body.get("msg")
        if isinstance(body_msg, str):
            return body_msg.strip()

    return ""


def extract_audience_count(payload: Dict[str, Any]) -> int:
    direct_count = payload.get("audience_count")

    if isinstance(direct_count, int) and direct_count >= 0:
        return direct_count

    audience = payload.get("audience")

    if isinstance(audience, dict):
        count = audience.get("count")
        if isinstance(count, int) and count >= 0:
            return count

        segment = audience.get("segment")
        if segment == "all-members":
            return 100

        if segment:
            return 50

    return 100


def extract_message_subject(payload: Dict[str, Any], fallback_title: str) -> str:
    message = payload.get("message")

    if isinstance(message, dict):
        title = message.get("title") or message.get("subject")
        if isinstance(title, str) and title.strip():
            return title.strip()

    subject = payload.get("subject")
    if isinstance(subject, str) and subject.strip():
        return subject.strip()

    return fallback_title


def build_platform_messages(
    payload: Dict[str, Any],
    title: str,
    body: str,
) -> Dict[str, Dict[str, Any]]:
    subject = extract_message_subject(payload, title)
    message_type = "discord_embed"

    raw_message = payload.get("message")
    if isinstance(raw_message, dict) and raw_message.get("format") == "text":
        message_type = "discord_text"

    discord_message: Dict[str, Any] = {
        "type": message_type,
        "title": subject,
        "body": body,
    }

    if isinstance(raw_message, dict):
        color = raw_message.get("color")
        if isinstance(color, (str, int)) and color not in ("", None):
            discord_message["color"] = color
        thumbnail = raw_message.get("thumbnail_url")
        if isinstance(thumbnail, str) and thumbnail.strip():
            discord_message["thumbnail_url"] = thumbnail.strip()
        image = raw_message.get("image_url")
        if isinstance(image, str) and image.strip():
            discord_message["image_url"] = image.strip()

    return {"discord": discord_message}


def extract_discord_channel_id(payload: Dict[str, Any]) -> str | None:
    channel_id = payload.get("discord_channel_id")

    if isinstance(channel_id, str) and channel_id.strip().isdigit():
        return channel_id.strip()

    return None


def extract_snowflake(payload: Dict[str, Any], field: str) -> str | None:
    value = payload.get(field)

    if isinstance(value, str) and value.strip().isdigit():
        return value.strip()

    return None


def extract_role_id_list(payload: Dict[str, Any], field: str) -> list[str]:
    value = payload.get(field)

    if not isinstance(value, list):
        return []

    return [str(item) for item in value if str(item).isdigit()]


def extract_delivery_target(payload: Dict[str, Any]) -> str:
    target = payload.get("delivery_target")
    return "dm" if target == "dm" else "channel"


async def get_queue_state_value(redis_client) -> str:
    value = await redis_client.get(QUEUE_STATE_KEY)

    if isinstance(value, bytes):
        value = value.decode("utf-8")

    if value not in ["running", "paused"]:
        return "running"

    return value


def _campaign_guild_id(campaign: Dict[str, Any] | None) -> str | None:
    if not isinstance(campaign, dict):
        return None
    value = campaign.get("guild_id")
    if isinstance(value, str) and value.strip().isdigit():
        return value.strip()
    return None


def _filter_campaigns_for_operator(
    campaigns: list[Dict[str, Any]],
    allowed_guild_ids: set[str],
) -> list[Dict[str, Any]]:
    if "*" in allowed_guild_ids:
        return campaigns
    return [
        campaign
        for campaign in campaigns
        if _campaign_guild_id(campaign) in allowed_guild_ids
    ]


async def _assert_campaign_access(
    campaign: Dict[str, Any],
    *,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService,
    settings: Settings,
) -> None:
    guild_id = _campaign_guild_id(campaign)
    if not guild_id:
        raise HTTPException(
            status_code=403,
            detail="Campaign is missing a guild and cannot be accessed.",
        )
    await require_guild_manager(guild_id, session, http_client, sessions, settings)


@router.get("")
async def list_campaigns(
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=100, ge=1, le=200),
):
    redis_client = await get_redis()

    try:
        allowed = await operator_manageable_guild_ids(
            session, http_client, sessions, settings
        )
        campaigns = _filter_campaigns_for_operator(
            await store_list_campaigns(redis_client),
            allowed,
        )[:limit]
        return [normalize_campaign(campaign) for campaign in campaigns]
    finally:
        await redis_client.aclose()


@router.get("/stats")
async def get_stats(
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        allowed = await operator_manageable_guild_ids(
            session, http_client, sessions, settings
        )
        campaigns = [
            normalize_campaign(campaign)
            for campaign in _filter_campaigns_for_operator(
                await store_list_campaigns(redis_client),
                allowed,
            )
        ]

        return {
            "total_campaigns": len(campaigns),
            "total_audience": sum(safe_int(c.get("audience_count")) for c in campaigns),
            "total_sent": sum(safe_int(c.get("sent_count")) for c in campaigns),
            "total_failed": sum(safe_int(c.get("failed_count")) for c in campaigns),
            "total_permanent_failed": sum(
                safe_int(c.get("permanent_failed_count")) for c in campaigns
            ),
            "total_retries": sum(safe_int(c.get("retry_count")) for c in campaigns),
            "running_count": sum(1 for c in campaigns if c.get("status") == "running"),
            "scheduled_count": sum(
                1 for c in campaigns if c.get("status") == "scheduled"
            ),
            "completed_count": sum(
                1 for c in campaigns if c.get("status") == "completed"
            ),
            "failed_campaign_count": sum(
                1 for c in campaigns if c.get("status") == "failed"
            ),
            "completed_with_failures_count": sum(
                1
                for c in campaigns
                if c.get("status") in ("completed", "failed")
                and safe_int(c.get("permanent_failed_count")) > 0
            ),
        }
    finally:
        await redis_client.aclose()


@router.get("/activity")
async def get_activity(
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        allowed = await operator_manageable_guild_ids(
            session, http_client, sessions, settings
        )
        items = await store_list_activity(redis_client, limit=80)
        if "*" in allowed:
            return items[:30]
        campaign_ids: set[str] = set()
        for campaign in _filter_campaigns_for_operator(
            await store_list_campaigns(redis_client),
            allowed,
        ):
            campaign_id = campaign.get("id")
            if isinstance(campaign_id, str):
                campaign_ids.add(campaign_id)
        return [
            item
            for item in items
            if isinstance(item, dict) and item.get("campaign_id") in campaign_ids
        ][:30]
    finally:
        await redis_client.aclose()


@router.get("/queue/state")
async def get_queue_state(
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        state = await get_queue_state_value(redis_client)
        allowed = await operator_manageable_guild_ids(
            session, http_client, sessions, settings
        )
        campaigns = _filter_campaigns_for_operator(
            await store_list_campaigns(redis_client),
            allowed,
        )

        queued_count = sum(1 for campaign in campaigns if campaign.get("status") == "queued")
        running_count = sum(
            1 for campaign in campaigns if campaign.get("status") == "running"
        )
        scheduled_count = sum(
            1 for campaign in campaigns if campaign.get("status") == "scheduled"
        )

        return {
            "state": state,
            "is_paused": state == "paused",
            "queued_count": queued_count,
            "running_count": running_count,
            "scheduled_count": scheduled_count,
            "updated_at": now_iso(),
        }
    finally:
        await redis_client.aclose()


@public_router.get("/worker/health")
async def get_worker_health():
    """Unauthenticated heartbeat probe (same pattern as /bot/health)."""
    redis_client = await get_redis()

    try:
        heartbeat = await redis_client.get(WORKER_HEARTBEAT_KEY)

        if isinstance(heartbeat, bytes):
            heartbeat = heartbeat.decode("utf-8")

        return {
            "online": bool(heartbeat),
            "last_heartbeat": heartbeat,
            "checked_at": now_iso(),
        }
    finally:
        await redis_client.aclose()


@router.get("/unsubscribed/{guild_id}")
async def list_campaign_unsubscribed(
    guild_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Ops listing of members who opted out of campaign DMs."""

    await require_guild_manager(guild_id, session, http_client, sessions, settings)
    redis_client = await get_redis()

    try:
        user_ids = await list_unsubscribed_user_ids(redis_client, guild_id=guild_id)
    finally:
        await redis_client.aclose()

    return {"guild_id": guild_id, "user_ids": user_ids, "count": len(user_ids)}


@router.post("/queue/pause", dependencies=[Depends(require_platform_admin)])
async def pause_queue():
    redis_client = await get_redis()

    try:
        await redis_client.set(QUEUE_STATE_KEY, "paused")

        return {
            "ok": True,
            "state": "paused",
            "is_paused": True,
            "message": "Campaign queue paused. Worker will stop dispatching new queued executions.",
            "updated_at": now_iso(),
        }
    finally:
        await redis_client.aclose()


@router.post("/queue/resume", dependencies=[Depends(require_platform_admin)])
async def resume_queue():
    redis_client = await get_redis()

    try:
        await redis_client.set(QUEUE_STATE_KEY, "running")

        return {
            "ok": True,
            "state": "running",
            "is_paused": False,
            "message": "Campaign queue resumed. Worker can dispatch queued executions.",
            "updated_at": now_iso(),
        }
    finally:
        await redis_client.aclose()


@router.post("/rehydrate-runtime", dependencies=[Depends(require_platform_admin)])
async def rehydrate_campaign_runtime():
    """Rebuild Redis queue and schedule indexes from Postgres campaign statuses."""
    redis_client = await get_redis()
    try:
        await redis_client.delete("norgoth:campaign_execution_queue")
        await redis_client.delete("norgoth:campaign_scheduled")
        queued = await list_campaigns_by_statuses(redis_client, ["queued"])
        scheduled = await list_campaigns_by_statuses(redis_client, ["scheduled"])
        rebuilt_queue = 0
        rebuilt_schedule = 0

        for campaign in queued:
            await enqueue_campaign(redis_client, campaign["id"])
            rebuilt_queue += 1

        for campaign in scheduled:
            if await schedule_campaign(redis_client, campaign):
                rebuilt_schedule += 1

        return {
            "ok": True,
            "queued_rebuilt": rebuilt_queue,
            "scheduled_rebuilt": rebuilt_schedule,
            "checked_at": now_iso(),
        }
    finally:
        await redis_client.aclose()


@router.get("/{campaign_id}/activity")
async def get_campaign_activity(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        return await store_list_activity(redis_client, campaign_id=campaign_id, limit=30)
    finally:
        await redis_client.aclose()


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


@router.post("")
async def create_campaign(
    payload: Dict[str, Any],
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign_id = str(uuid.uuid4())
        timestamp = now_iso()

        title = extract_title(payload)
        message = extract_message(payload)
        audience_count = extract_audience_count(payload)
        launch_at = payload.get("launch_at")
        guild_id = extract_snowflake(payload, "guild_id")
        if not guild_id:
            raise HTTPException(
                status_code=422,
                detail="guild_id is required for durable campaign persistence.",
            )
        await require_guild_manager(
            guild_id, session, http_client, sessions, settings
        )

        requested_status = payload.get("status")
        status = "scheduled" if launch_at else requested_status or "draft"

        if status not in ("draft", "scheduled", "queued"):
            status = "draft"

        campaign = {
            "id": campaign_id,
            "title": title,
            "message": message,
            "platform_messages": build_platform_messages(payload, title, message),
            "audience_count": audience_count,
            "status": status,
            "sent_count": 0,
            "failed_count": 0,
            "retry_count": 0,
            "permanent_failed_count": 0,
            "executed_at": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "type": payload.get("type"),
            "audience": payload.get("audience"),
            "platforms": ["discord"],
            "delivery_target": extract_delivery_target(payload),
            "guild_id": guild_id,
            "discord_channel_id": extract_discord_channel_id(payload),
            "dm_include_role_ids": extract_role_id_list(payload, "dm_include_role_ids"),
            "dm_exclude_role_ids": extract_role_id_list(payload, "dm_exclude_role_ids"),
            "locales": payload.get("locales"),
            "tags": payload.get("tags"),
            "risk_level": payload.get("risk_level"),
            "launch_at": launch_at,
            "raw_payload": payload,
        }

        await save_campaign(redis_client, campaign)
        await add_activity(redis_client, campaign, "created", "Campaign created.")

        if status == "queued":
            await add_activity(
                redis_client,
                campaign,
                "queued",
                "Campaign queued for immediate delivery.",
            )
            await enqueue_campaign(redis_client, campaign_id)

        if status == "scheduled":
            scheduled = await schedule_campaign(redis_client, campaign)

            if scheduled:
                await add_activity(
                    redis_client,
                    campaign,
                    "scheduled",
                    f"Campaign scheduled for automatic execution at {launch_at}.",
                )
            else:
                campaign["status"] = "draft"
                campaign["launch_at"] = None
                await save_campaign(redis_client, campaign)
                await add_activity(
                    redis_client,
                    campaign,
                    "schedule_invalid",
                    "Invalid launch_at. Campaign saved as draft.",
                )

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    payload: CampaignUpdate,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        if campaign.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail="Running campaigns cannot be edited",
            )

        campaign = normalize_campaign(campaign)
        update_data = payload.model_dump(exclude_unset=True)
        if "guild_id" in update_data and update_data["guild_id"]:
            await require_guild_manager(
                str(update_data["guild_id"]),
                session,
                http_client,
                sessions,
                settings,
            )

        if "title" in update_data and update_data["title"]:
            campaign["title"] = update_data["title"]

        if "name" in update_data and update_data["name"]:
            campaign["title"] = update_data["name"]

        if "description" in update_data:
            raw = campaign.get("raw_payload")
            if not isinstance(raw, dict):
                raw = {}
            raw = {**raw, "description": update_data["description"] or ""}
            campaign["raw_payload"] = raw
            campaign["description"] = update_data["description"] or ""

        if "message" in update_data and isinstance(update_data["message"], str):
            campaign["message"] = update_data["message"]

        if "body" in update_data:
            body = update_data["body"]

            if isinstance(body, str):
                campaign["message"] = body

            if isinstance(body, dict):
                body_message = body.get("message") or body.get("msg")
                if isinstance(body_message, str):
                    campaign["message"] = body_message

        if "message" in update_data or "body" in update_data:
            campaign["platform_messages"] = build_platform_messages(
                update_data,
                campaign["title"],
                campaign.get("message", ""),
            )

        if "audience_count" in update_data and update_data["audience_count"] is not None:
            campaign["audience_count"] = update_data["audience_count"]

        for field_name in [
            "type",
            "audience",
            "locales",
            "tags",
            "risk_level",
            "launch_at",
            "discord_channel_id",
            "delivery_target",
            "guild_id",
            "dm_include_role_ids",
            "dm_exclude_role_ids",
        ]:
            if field_name in update_data:
                campaign[field_name] = update_data[field_name]

        if "status" in update_data and update_data["status"]:
            campaign["status"] = update_data["status"]

        if campaign.get("launch_at") and campaign.get("status") not in [
            "running",
            "completed",
        ]:
            campaign["status"] = "scheduled"
            await schedule_campaign(redis_client, campaign)
        else:
            await unschedule_campaign(redis_client, campaign_id)

        campaign["updated_at"] = now_iso()

        await save_campaign(redis_client, campaign)
        await add_activity(redis_client, campaign, "updated", "Campaign updated.")

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        await add_activity(redis_client, campaign, "deleted", "Campaign deleted.")
        await store_delete_campaign(redis_client, campaign_id)

        return {"ok": True, "deleted_id": campaign_id}
    finally:
        await redis_client.aclose()


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        if campaign.get("status") == "running":
            return normalize_campaign(campaign)

        await unschedule_campaign(redis_client, campaign_id)

        campaign = normalize_campaign(campaign)
        campaign["status"] = "queued"
        campaign["updated_at"] = now_iso()

        await save_campaign(redis_client, campaign)
        await add_activity(redis_client, campaign, "queued", "Campaign manually queued.")
        await enqueue_campaign(redis_client, campaign_id)

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


@router.post("/{campaign_id}/stop")
async def stop_campaign(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        await unschedule_campaign(redis_client, campaign_id)

        campaign = normalize_campaign(campaign)
        campaign["status"] = "stopped"
        campaign["updated_at"] = now_iso()

        await save_campaign(redis_client, campaign)
        await add_activity(redis_client, campaign, "stopped", "Campaign stopped by user.")

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


@router.post("/{campaign_id}/complete")
async def complete_campaign(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        await unschedule_campaign(redis_client, campaign_id)

        campaign = normalize_campaign(campaign)
        campaign["sent_count"] = safe_int(campaign.get("audience_count"))
        campaign["failed_count"] = 0
        campaign["retry_count"] = 0
        campaign["permanent_failed_count"] = 0
        campaign["status"] = "completed"
        campaign["executed_at"] = campaign.get("executed_at") or now_iso()
        campaign["updated_at"] = now_iso()

        await save_campaign(redis_client, campaign)
        await add_activity(
            redis_client,
            campaign,
            "manual_completed",
            "Campaign manually completed.",
        )

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


@router.post("/{campaign_id}/execute")
async def execute_campaign(
    campaign_id: str,
    session: OperatorSessionDependency,
    http_client: HTTPClientDependency,
    sessions: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    redis_client = await get_redis()

    try:
        campaign = await store_get_campaign(redis_client, campaign_id)

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _assert_campaign_access(
            campaign,
            session=session,
            http_client=http_client,
            sessions=sessions,
            settings=settings,
        )

        if campaign.get("status") in ["queued", "running"]:
            return normalize_campaign(campaign)

        await unschedule_campaign(redis_client, campaign_id)

        campaign = normalize_campaign(campaign)
        campaign["sent_count"] = 0
        campaign["failed_count"] = 0
        campaign["retry_count"] = 0
        campaign["permanent_failed_count"] = 0
        campaign["status"] = "queued"
        campaign["executed_at"] = now_iso()
        campaign["updated_at"] = now_iso()

        await save_campaign(redis_client, campaign)
        await add_activity(redis_client, campaign, "queued", "Campaign execution requested.")
        await enqueue_campaign(redis_client, campaign_id)

        return normalize_campaign(campaign)
    finally:
        await redis_client.aclose()


class InternalUnsubscribeBody(BaseModel):
    guild_id: str = Field(pattern=r"^[0-9]{5,25}$")
    user_id: str = Field(pattern=r"^[0-9]{5,25}$")


@internal_router.post("/unsubscribe", dependencies=[Depends(require_internal_token)])
async def mark_campaign_unsubscribed_internal(
    body: InternalUnsubscribeBody,
) -> dict[str, Any]:
    redis_client = await get_redis()
    try:
        await mark_unsubscribed(
            redis_client,
            guild_id=body.guild_id,
            user_id=body.user_id,
        )
        return {"ok": True, "guild_id": body.guild_id, "user_id": body.user_id}
    finally:
        await redis_client.aclose()
