"""Norgoth campaign worker: delivers campaigns to Discord channels and DMs.

Watches the Redis schedule/queue and, for each due campaign, either posts the
campaign message to its configured Discord channel or DMs every targeted
member, using the bot token.
Run from Norgoth/apps/api: .venv/bin/python -m app.workers.campaign_worker
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from app.services.campaign_store import (
    add_activity,
    claim_campaign_for_execution,
    enqueue_campaign,
    get_campaign,
    get_due_scheduled_campaign_ids,
    get_redis,
    list_campaigns_by_statuses,
    list_unsubscribed_user_ids,
    now_iso,
    pop_execution_campaign_id,
    release_campaign_claim,
    schedule_campaign,
    save_campaign,
    unschedule_campaign,
)
from app.services.discord.embed_builder import build_embed_dict
from app.services.template_variables import (
    USER_NAME_FALLBACK,
    resolve_user_name_from_recipient,
)

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

MAX_RETRY_ROUNDS = 2
RETRY_DELAY_SECONDS = 10

# Discord tolerates roughly 1 DM-create/send per second for bots before
# hitting hard rate limits; stay just under that.
DM_SEND_INTERVAL_SECONDS = 1.2
DM_MAX_ATTEMPTS = 2

QUEUE_STATE_KEY = "norgoth:campaign_queue_state"
WORKER_HEARTBEAT_KEY = "norgoth:worker:heartbeat"
REHYDRATE_ON_START = os.getenv("NORGOTH_CAMPAIGN_REHYDRATE_ON_START", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def render_campaign_text(
    text: str,
    *,
    user_name: str,
    server_name: str,
    campaign_name: str,
) -> str:
    return (
        text.replace("{user_name}", user_name)
        .replace("{server_name}", server_name)
        .replace("{campaign_name}", campaign_name)
    )


async def get_guild_context(redis_client, guild_id: str | None) -> Dict[str, Any]:
    """Server name + member snapshot the bot published for this guild."""

    context: Dict[str, Any] = {"server_name": "the server", "members": []}

    if not guild_id:
        return context

    raw_resources = await redis_client.get(f"norgoth:guild:{guild_id}:resources")

    if raw_resources:
        try:
            resources = json.loads(raw_resources)
            if isinstance(resources, dict) and resources.get("guild_name"):
                context["server_name"] = str(resources["guild_name"])
        except json.JSONDecodeError:
            pass

    raw_members = await redis_client.get(f"norgoth:guild:{guild_id}:members")

    if raw_members:
        try:
            snapshot = json.loads(raw_members)
            if isinstance(snapshot, dict) and isinstance(
                snapshot.get("members"), list
            ):
                context["members"] = snapshot["members"]
        except json.JSONDecodeError:
            pass

    return context


def unsubscribed_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:campaigns:unsubscribed"


def resolve_dm_recipients(campaign: Dict[str, Any], members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    include_roles = set(campaign.get("dm_include_role_ids") or [])
    exclude_roles = set(campaign.get("dm_exclude_role_ids") or [])

    recipients = []

    for member in members:
        if not isinstance(member, dict) or member.get("bot"):
            continue

        member_roles = set(member.get("role_ids") or [])

        if include_roles and not (member_roles & include_roles):
            continue

        if member_roles & exclude_roles:
            continue

        recipients.append(member)

    return recipients


async def filter_unsubscribed(
    redis_client,
    guild_id: str,
    recipients: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not guild_id:
        return recipients

    unsubscribed = set(
        await list_unsubscribed_user_ids(redis_client, guild_id=guild_id)
    )

    if not unsubscribed:
        return recipients

    return [
        member
        for member in recipients
        if str(member.get("id")) not in unsubscribed
    ]


async def is_queue_paused(redis_client) -> bool:
    value = await redis_client.get(QUEUE_STATE_KEY)

    if isinstance(value, bytes):
        value = value.decode("utf-8")

    return value == "paused"


async def heartbeat_tick() -> None:
    redis_client = await get_redis()

    try:
        await redis_client.set(WORKER_HEARTBEAT_KEY, now_iso(), ex=45)
    finally:
        await redis_client.aclose()


def build_message_payload(
    campaign: Dict[str, Any],
    *,
    user_name: str,
    server_name: str,
    guild_id: str | None = None,
    include_unsubscribe: bool = False,
) -> Dict[str, Any]:
    campaign_name = str(campaign.get("title") or "Campaign")
    raw_body = str(campaign.get("message") or "")

    platform_messages = campaign.get("platform_messages")
    message_type = "discord_embed"
    raw_subject = campaign_name
    embed_color: Any = None
    embed_thumbnail: str | None = None
    embed_image: str | None = None

    if isinstance(platform_messages, dict):
        discord_message = platform_messages.get("discord")
        if isinstance(discord_message, dict):
            if discord_message.get("type"):
                message_type = str(discord_message["type"])
            if discord_message.get("title"):
                raw_subject = str(discord_message["title"])
            embed_color = discord_message.get("color")
            thumb = discord_message.get("thumbnail_url")
            if isinstance(thumb, str) and thumb.strip():
                embed_thumbnail = thumb.strip()
            img = discord_message.get("image_url")
            if isinstance(img, str) and img.strip():
                embed_image = img.strip()

    body = render_campaign_text(
        raw_body,
        user_name=user_name,
        server_name=server_name,
        campaign_name=campaign_name,
    )
    subject = render_campaign_text(
        raw_subject,
        user_name=user_name,
        server_name=server_name,
        campaign_name=campaign_name,
    )

    footer_text = "Norgoth Campaign"
    if include_unsubscribe:
        footer_text = (
            "Norgoth Campaign · Use Unsubscribe or /unsubscribe to opt out"
        )

    if message_type == "discord_text":
        content = body[:2000] or subject[:2000]
        if include_unsubscribe:
            content = f"{content}\n\n_Reply /unsubscribe in the server to opt out._"[:2000]
        payload: Dict[str, Any] = {"content": content}
    else:
        embed = build_embed_dict(
            {
                "title": subject,
                "description": body,
                "color": embed_color,
                "thumbnail_url": embed_thumbnail,
                "image_url": embed_image,
                "footer": footer_text,
            },
            default_color=0x18181B,
        )
        payload = {"embeds": [embed]} if embed else {"content": subject[:2000]}

    if include_unsubscribe and guild_id:
        payload["components"] = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 2,
                        "label": "Unsubscribe",
                        "custom_id": f"norgoth:campaigns:unsub:{guild_id}",
                    }
                ],
            }
        ]

    return payload


async def discord_post(
    client: httpx.AsyncClient,
    path: str,
    payload: Dict[str, Any],
) -> tuple[bool, Dict[str, Any] | str]:
    """POST to the Discord API. Returns (success, json_or_error)."""

    try:
        response = await client.post(
            f"{DISCORD_API_BASE_URL}{path}",
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            json=payload,
        )
    except httpx.HTTPError as error:
        return False, f"network error: {error}"

    if response.status_code in (200, 201):
        data = response.json()
        return True, data if isinstance(data, dict) else {}

    return False, f"HTTP {response.status_code}: {response.text[:300]}"


async def send_campaign_message(
    channel_id: str,
    payload: Dict[str, Any],
) -> tuple[bool, str]:
    """Post to the Discord channel. Returns (success, message_id_or_error)."""

    async with httpx.AsyncClient(timeout=15.0) as client:
        success, result = await discord_post(
            client,
            f"/channels/{channel_id}/messages",
            payload,
        )

    if success and isinstance(result, dict):
        return True, str(result.get("id", "unknown"))

    return False, str(result)


async def send_direct_message(
    client: httpx.AsyncClient,
    user_id: str,
    payload: Dict[str, Any],
) -> tuple[bool, str]:
    """Open (or reuse) the DM channel with a user and send the message."""

    success, result = await discord_post(
        client,
        "/users/@me/channels",
        {"recipient_id": user_id},
    )

    if not success or not isinstance(result, dict):
        return False, f"could not open DM channel: {result}"

    dm_channel_id = result.get("id")

    if not dm_channel_id:
        return False, "DM channel response had no id"

    success, result = await discord_post(
        client,
        f"/channels/{dm_channel_id}/messages",
        payload,
    )

    if success and isinstance(result, dict):
        return True, str(result.get("id", "unknown"))

    return False, str(result)


async def fail_campaign(
    redis_client,
    campaign: Dict[str, Any],
    reason: str,
) -> None:
    campaign["status"] = "failed"
    campaign["failed_count"] = max(int(campaign.get("failed_count") or 0), 1)
    campaign["permanent_failed_count"] = max(
        int(campaign.get("permanent_failed_count") or 0), 1
    )
    campaign["platform_results"] = {
        "discord": {
            "sent_count": int(campaign.get("sent_count") or 0),
            "failed_count": campaign["failed_count"],
            "retry_count": campaign.get("retry_count", 0),
            "permanent_failed_count": campaign["permanent_failed_count"],
        }
    }
    campaign["updated_at"] = now_iso()

    await save_campaign(redis_client, campaign)
    await add_activity(
        redis_client,
        campaign,
        "completed_with_failures",
        f"Discord delivery failed permanently: {reason}",
    )


async def execute_channel_campaign(
    redis_client,
    campaign: Dict[str, Any],
    server_name: str,
) -> None:
    campaign_id = campaign["id"]
    channel_id = campaign.get("discord_channel_id")

    if not channel_id:
        await fail_campaign(
            redis_client,
            campaign,
            "No Discord channel selected for this campaign.",
        )
        return

    await add_activity(
        redis_client,
        campaign,
        "running",
        f"Delivering campaign to Discord channel {channel_id}.",
    )

    payload = build_message_payload(
        campaign,
        # Channel campaigns have no per-recipient context; use the shared
        # neutral fallback (never a greeting like "there").
        user_name=USER_NAME_FALLBACK,
        server_name=server_name,
    )
    attempt = 0
    success = False
    detail = ""

    while attempt <= MAX_RETRY_ROUNDS:
        current = await get_campaign(redis_client, campaign_id)

        if not current or current.get("status") == "stopped":
            await add_activity(
                redis_client,
                campaign,
                "stopped",
                "Delivery cancelled because the campaign was stopped.",
            )
            return

        success, detail = await send_campaign_message(str(channel_id), payload)

        if success:
            break

        attempt += 1

        if attempt <= MAX_RETRY_ROUNDS:
            await add_activity(
                redis_client,
                campaign,
                "platform_retry_processed",
                f"Discord send failed ({detail}). Retry {attempt}/{MAX_RETRY_ROUNDS}.",
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    campaign = await get_campaign(redis_client, campaign_id) or campaign

    if success:
        campaign["status"] = "completed"
        campaign["sent_count"] = 1
        campaign["failed_count"] = 0
        campaign["retry_count"] = attempt
        campaign["permanent_failed_count"] = 0
        campaign["audience_count"] = 1
        campaign["discord_message_id"] = detail
        campaign["platform_results"] = {
            "discord": {
                "sent_count": 1,
                "failed_count": 0,
                "retry_count": attempt,
                "permanent_failed_count": 0,
            }
        }
        campaign["updated_at"] = now_iso()

        await save_campaign(redis_client, campaign)
        await add_activity(
            redis_client,
            campaign,
            "completed",
            f"Message delivered to channel {channel_id} "
            f"(Discord message id {detail}).",
        )
    else:
        campaign["retry_count"] = MAX_RETRY_ROUNDS
        await fail_campaign(redis_client, campaign, detail)


async def execute_dm_campaign(
    redis_client,
    campaign: Dict[str, Any],
    server_name: str,
    members: List[Dict[str, Any]],
) -> None:
    campaign_id = campaign["id"]
    recipients = resolve_dm_recipients(campaign, members)
    guild_id = str(campaign.get("guild_id") or "")
    recipients = await filter_unsubscribed(redis_client, guild_id, recipients)

    if not recipients:
        await fail_campaign(
            redis_client,
            campaign,
            "No members match the DM audience filters "
            "(or all matching members unsubscribed / no member snapshot yet).",
        )
        return

    campaign["audience_count"] = len(recipients)
    campaign["recipient_results"] = []
    await save_campaign(redis_client, campaign)

    await add_activity(
        redis_client,
        campaign,
        "running",
        f"Delivering campaign via DM to {len(recipients)} members.",
    )

    sent_count = 0
    failed_count = 0
    retry_count = 0
    stopped = False

    async with httpx.AsyncClient(timeout=15.0) as client:
        for index, recipient in enumerate(recipients):
            current = await get_campaign(redis_client, campaign_id)

            if not current or current.get("status") == "stopped":
                stopped = True
                break

            if await is_queue_paused(redis_client):
                # Pause gates new campaign dispatch AND in-flight DM fan-out.
                while await is_queue_paused(redis_client):
                    await asyncio.sleep(2)

                    check = await get_campaign(redis_client, campaign_id)
                    if not check or check.get("status") == "stopped":
                        stopped = True
                        break

                if stopped:
                    break

            payload = build_message_payload(
                campaign,
                user_name=resolve_user_name_from_recipient(recipient),
                server_name=server_name,
                guild_id=guild_id,
                include_unsubscribe=True,
            )

            success = False
            detail = ""
            attempts = 0

            while attempts < DM_MAX_ATTEMPTS:
                attempts += 1
                success, detail = await send_direct_message(
                    client,
                    str(recipient["id"]),
                    payload,
                )

                if success:
                    break

                if attempts < DM_MAX_ATTEMPTS:
                    retry_count += 1
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

            result_entry = {
                "user_id": str(recipient.get("id")),
                "user_name": str(recipient.get("name") or ""),
                "status": "sent" if success else "failed",
                "attempts": attempts,
                "error": None if success else detail[:200],
                "at": now_iso(),
            }

            if success:
                sent_count += 1
            else:
                failed_count += 1

            # Persist progress after every recipient so the dashboard
            # sees live counts during long fan-outs.
            campaign = await get_campaign(redis_client, campaign_id) or campaign
            results = campaign.get("recipient_results") or []
            results.append(result_entry)
            campaign["recipient_results"] = results[-1000:]
            campaign["sent_count"] = sent_count
            campaign["failed_count"] = failed_count
            campaign["retry_count"] = retry_count
            campaign["permanent_failed_count"] = failed_count
            await save_campaign(redis_client, campaign)

            if index < len(recipients) - 1:
                await asyncio.sleep(DM_SEND_INTERVAL_SECONDS)

    campaign = await get_campaign(redis_client, campaign_id) or campaign
    campaign["sent_count"] = sent_count
    campaign["failed_count"] = failed_count
    campaign["retry_count"] = retry_count
    campaign["permanent_failed_count"] = failed_count
    campaign["platform_results"] = {
        "discord": {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "retry_count": retry_count,
            "permanent_failed_count": failed_count,
        }
    }

    if stopped:
        campaign["status"] = "stopped"
        await save_campaign(redis_client, campaign)
        await add_activity(
            redis_client,
            campaign,
            "stopped",
            f"DM delivery stopped after {sent_count} sends "
            f"({failed_count} failures).",
        )
        return

    if sent_count == 0:
        await fail_campaign(
            redis_client,
            campaign,
            f"All {failed_count} DM deliveries failed.",
        )
        return

    campaign["status"] = "completed"
    campaign["updated_at"] = now_iso()
    await save_campaign(redis_client, campaign)

    if failed_count:
        await add_activity(
            redis_client,
            campaign,
            "completed_with_failures",
            f"DM delivery finished: {sent_count} sent, {failed_count} failed "
            "(users may have DMs disabled).",
        )
    else:
        await add_activity(
            redis_client,
            campaign,
            "completed",
            f"DM delivery finished: all {sent_count} messages sent.",
        )


async def execute_campaign(campaign_id: str) -> None:
    redis_client = await get_redis()

    try:
        if not await claim_campaign_for_execution(redis_client, campaign_id):
            return

        campaign = await get_campaign(redis_client, campaign_id)

        if not campaign:
            return

        if campaign.get("status") in ["completed", "failed", "running"]:
            return

        campaign["status"] = "running"
        campaign["executed_at"] = campaign.get("executed_at") or now_iso()
        campaign["platforms"] = ["discord"]
        campaign["sent_count"] = 0
        campaign["failed_count"] = 0
        campaign["retry_count"] = 0
        campaign["permanent_failed_count"] = 0
        campaign["updated_at"] = now_iso()
        await save_campaign(redis_client, campaign)

        if not DISCORD_BOT_TOKEN:
            await fail_campaign(
                redis_client,
                campaign,
                "DISCORD_BOT_TOKEN is not configured in Norgoth/.env.",
            )
            return

        context = await get_guild_context(redis_client, campaign.get("guild_id"))
        server_name = str(context["server_name"])

        if campaign.get("delivery_target") == "dm":
            await execute_dm_campaign(
                redis_client,
                campaign,
                server_name,
                context["members"],
            )
        else:
            await execute_channel_campaign(redis_client, campaign, server_name)
    finally:
        await release_campaign_claim(redis_client, campaign_id)
        await redis_client.aclose()


async def schedule_tick() -> None:
    redis_client = await get_redis()

    try:
        if await is_queue_paused(redis_client):
            return

        campaign_ids = await get_due_scheduled_campaign_ids(redis_client)

        for campaign_id in campaign_ids:
            campaign = await get_campaign(redis_client, campaign_id)

            if not campaign or campaign.get("status") != "scheduled":
                await unschedule_campaign(redis_client, campaign_id)
                continue

            await unschedule_campaign(redis_client, campaign_id)

            campaign["status"] = "queued"
            campaign["executed_at"] = now_iso()
            campaign["updated_at"] = now_iso()

            await save_campaign(redis_client, campaign)
            await add_activity(
                redis_client,
                campaign,
                "scheduled_execution_started",
                "launch_at reached. Campaign moved to execution queue.",
            )
            await enqueue_campaign(redis_client, campaign_id)
    finally:
        await redis_client.aclose()


async def execution_tick() -> None:
    redis_client = await get_redis()

    try:
        if await is_queue_paused(redis_client):
            return

        campaign_id = await pop_execution_campaign_id(redis_client)

        if campaign_id:
            asyncio.create_task(execute_campaign(campaign_id))
    finally:
        await redis_client.aclose()


async def rehydrate_runtime_indexes() -> None:
    """Rebuild Redis queue/schedule from durable campaign statuses."""
    redis_client = await get_redis()
    try:
        await redis_client.delete("norgoth:campaign_execution_queue")
        await redis_client.delete("norgoth:campaign_scheduled")
        queued = await list_campaigns_by_statuses(redis_client, ["queued"])
        scheduled = await list_campaigns_by_statuses(redis_client, ["scheduled"])

        for campaign in queued:
            await enqueue_campaign(redis_client, campaign["id"])
        for campaign in scheduled:
            await schedule_campaign(redis_client, campaign)
    finally:
        await redis_client.aclose()


async def worker_loop() -> None:
    print("Norgoth campaign worker started (real Discord delivery).")

    if not DISCORD_BOT_TOKEN:
        print(
            "WARNING: DISCORD_BOT_TOKEN is not set. "
            "Campaign sends will fail until it is configured in Norgoth/.env."
        )

    if REHYDRATE_ON_START:
        await rehydrate_runtime_indexes()

    while True:
        await heartbeat_tick()
        await schedule_tick()
        await execution_tick()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(worker_loop())
