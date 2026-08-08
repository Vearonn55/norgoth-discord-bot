"""Ticket system configuration, records, transcripts, and panel publishing."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import (
    guild_manager_dependency,
    require_operator_session,
)
from app.security.session import OperatorSession
from app.services.campaign_store import get_redis, now_iso

# Guild-scoped admin routes require guild-manager auth.
router = APIRouter(
    tags=["Tickets"],
    dependencies=[Depends(guild_manager_dependency())],
)

# Public share-token transcript lookup (intentionally unauthenticated: the
# 90-day token is the bearer secret).
public_router = APIRouter(tags=["Tickets"])

# Identity-bound transcript access: any logged-in Discord user, authorized
# per-request against the specific ticket (opener or support role). This is a
# lesser privilege than guild-manager, so it lives on its own router.
session_router = APIRouter(tags=["Tickets"])

DISCORD_API_BASE_URL = "https://discord.com/api/v10"
SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

OPEN_BUTTON_ID = "norgoth:ticket:open"
MAX_TICKET_PANELS = 25


def tickets_config_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:config"


def ticket_panels_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:panels"


def tickets_records_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:records"


def ticket_transcript_key(guild_id: str, ticket_id: str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:transcript:{ticket_id}"


def ticket_share_key(token: str) -> str:
    return f"norgoth:tickets:share:{token}"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


async def _load_ticket_record(guild_id: str, ticket_id: str) -> dict[str, Any] | None:
    redis_client = await get_redis()
    try:
        raw = await redis_client.hget(tickets_records_key(guild_id), ticket_id)
    finally:
        await redis_client.aclose()

    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _member_role_ids(guild_id: str, user_id: str) -> set[str]:
    """Best-effort role lookup from the bot-published member snapshot."""

    redis_client = await get_redis()
    try:
        raw = await redis_client.get(guild_members_key(guild_id))
    finally:
        await redis_client.aclose()

    if not raw:
        return set()
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError:
        return set()

    members = snapshot.get("members") if isinstance(snapshot, dict) else None
    if not isinstance(members, list):
        return set()
    for member in members:
        if isinstance(member, dict) and str(member.get("id")) == str(user_id):
            return {str(r) for r in (member.get("role_ids") or [])}
    return set()


class TicketsConfig(BaseModel):
    category_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    log_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    support_role_ids: list[str] = Field(default_factory=list)
    welcome_text: str = Field(
        default="Support will be with you shortly. Describe your issue here.",
        max_length=1000,
    )


@router.get("/guilds/{guild_id}/tickets/config")
async def get_tickets_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(tickets_config_key(guild_id))
    finally:
        await redis_client.aclose()

    defaults = TicketsConfig().model_dump()

    if not raw:
        return defaults

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return defaults

    if not isinstance(stored, dict):
        return defaults

    return {**defaults, **{k: v for k, v in stored.items() if k in defaults}}


@router.put("/guilds/{guild_id}/tickets/config")
async def update_tickets_config(
    guild_id: str,
    config: TicketsConfig,
) -> dict[str, Any]:
    payload = config.model_dump()
    payload["support_role_ids"] = [
        role_id
        for role_id in payload["support_role_ids"]
        if role_id.isdigit()
    ][:20]
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await redis_client.set(tickets_config_key(guild_id), json.dumps(payload))
    finally:
        await redis_client.aclose()

    return payload


@router.get("/guilds/{guild_id}/tickets")
async def list_tickets(guild_id: str) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        records = await redis_client.hgetall(tickets_records_key(guild_id))
    finally:
        await redis_client.aclose()

    tickets: list[dict[str, Any]] = []

    for raw in records.values():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            tickets.append(parsed)

    tickets.sort(key=lambda ticket: ticket.get("number", 0), reverse=True)
    return tickets


@router.get("/guilds/{guild_id}/tickets/{ticket_id}/transcript")
async def get_ticket_transcript(guild_id: str, ticket_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        transcript = await redis_client.get(
            ticket_transcript_key(guild_id, ticket_id)
        )
    finally:
        await redis_client.aclose()

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail="No transcript found; the ticket may still be open.",
        )

    return {"ticket_id": ticket_id, "transcript": transcript}


@public_router.get("/tickets/transcript/{token}")
async def get_shared_ticket_transcript(token: str) -> dict[str, Any]:
    """Public transcript lookup by share token (from close DM / log link)."""

    redis_client = await get_redis()

    try:
        raw = await redis_client.get(ticket_share_key(token))
    finally:
        await redis_client.aclose()

    if raw is None:
        raise HTTPException(
            status_code=404,
            detail="Transcript not found or the share link has expired.",
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail="Stored transcript is corrupted.",
        ) from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Invalid transcript payload.")

    return {
        "token": token,
        "guild_id": payload.get("guild_id"),
        "guild_name": payload.get("guild_name"),
        "ticket_id": payload.get("ticket_id"),
        "ticket_number": payload.get("ticket_number"),
        "opener_name": payload.get("opener_name"),
        "closed_by": payload.get("closed_by"),
        "closed_at": payload.get("closed_at"),
        "channel_name": payload.get("channel_name"),
        "transcript": payload.get("transcript") or "",
    }


@session_router.get("/guilds/{guild_id}/tickets/{ticket_id}/my-transcript")
async def get_own_ticket_transcript(
    guild_id: str,
    ticket_id: str,
    session: OperatorSession = Depends(require_operator_session),
) -> dict[str, Any]:
    """Return a ticket transcript to the opener or a support-role holder.

    This is identity-bound: a logged-in Discord user may only read a transcript
    for a ticket they opened, or for which they hold a configured support role.
    It is a least-privilege alternative to the guild-manager admin route and to
    the bearer share token.
    """

    record = await _load_ticket_record(guild_id, ticket_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    is_dev = session.user_id == "0"
    is_opener = str(record.get("opener_id") or "") == str(session.user_id)

    is_support = False
    if not is_opener and not is_dev:
        config = await get_tickets_config(guild_id)
        support_roles = {str(r) for r in (config.get("support_role_ids") or [])}
        if support_roles:
            member_roles = await _member_role_ids(guild_id, session.user_id)
            is_support = bool(support_roles & member_roles)

    if not (is_opener or is_support or is_dev):
        raise HTTPException(
            status_code=403,
            detail="You may only view transcripts for your own tickets.",
        )

    redis_client = await get_redis()
    try:
        transcript = await redis_client.get(
            ticket_transcript_key(guild_id, ticket_id)
        )
    finally:
        await redis_client.aclose()

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail="No transcript found; the ticket may still be open.",
        )

    return {
        "ticket_id": ticket_id,
        "ticket_number": record.get("number"),
        "opener_name": record.get("opener_name"),
        "closed_by": record.get("closed_by"),
        "closed_at": record.get("closed_at"),
        "viewer_role": "opener" if is_opener else "support",
        "transcript": transcript,
    }


# ── Multi-panel ticket panels ───────────────────────────────────────────────
# Mirrors the role_menus pattern: panels are stored as a list, saved via a
# full-list PUT (create/update/delete), and published individually. Publishing
# edits the previously posted message when possible so edits sync in place.


class TicketPanel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1, max_length=100)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    title: str = Field(default="Need help?", max_length=256)
    description: str = Field(
        default="Click the button below to open a private support ticket.",
        max_length=2000,
    )
    button_label: str = Field(default="Open Ticket", max_length=80)
    message_id: Optional[str] = None
    published_at: Optional[str] = None
    updated_at: Optional[str] = None


class TicketPanelsUpdate(BaseModel):
    panels: list[TicketPanel] = Field(
        default_factory=list, max_length=MAX_TICKET_PANELS
    )


async def read_ticket_panels(guild_id: str) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(ticket_panels_key(guild_id))
    finally:
        await redis_client.aclose()

    if not raw:
        return []

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return []

    panels = stored.get("panels") if isinstance(stored, dict) else None
    return panels if isinstance(panels, list) else []


async def write_ticket_panels(
    guild_id: str, panels: list[dict[str, Any]]
) -> None:
    redis_client = await get_redis()

    try:
        await redis_client.set(
            ticket_panels_key(guild_id),
            json.dumps({"panels": panels, "updated_at": now_iso()}),
        )
    finally:
        await redis_client.aclose()


@router.get("/guilds/{guild_id}/tickets/panels")
async def get_ticket_panels(guild_id: str) -> dict[str, Any]:
    return {"panels": await read_ticket_panels(guild_id)}


@router.put("/guilds/{guild_id}/tickets/panels")
async def update_ticket_panels(
    guild_id: str,
    payload: TicketPanelsUpdate,
) -> dict[str, Any]:
    existing = {
        panel.get("id"): panel for panel in await read_ticket_panels(guild_id)
    }

    panels: list[dict[str, Any]] = []
    for panel in payload.panels:
        record = panel.model_dump()
        prior = existing.get(record["id"])
        # Preserve publish state across edits; publishing updates it explicitly.
        if prior:
            record["message_id"] = prior.get("message_id")
            record["published_at"] = prior.get("published_at")
        record["updated_at"] = now_iso()
        panels.append(record)

    await write_ticket_panels(guild_id, panels)
    return {"panels": panels}


@router.post("/guilds/{guild_id}/tickets/panels/{panel_id}/publish")
async def publish_ticket_panel_by_id(
    guild_id: str, panel_id: str
) -> dict[str, Any]:
    """Post (or edit) a specific ticket panel with an Open Ticket button."""

    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="DISCORD_BOT_TOKEN is not configured in Norgoth/.env.",
        )

    panels = await read_ticket_panels(guild_id)
    panel = next((item for item in panels if item.get("id") == panel_id), None)

    if panel is None:
        raise HTTPException(status_code=404, detail="Ticket panel not found.")

    channel_id = panel.get("channel_id")

    if not channel_id:
        raise HTTPException(
            status_code=400,
            detail="The panel has no target channel configured.",
        )

    message_payload: dict[str, Any] = {
        "embeds": [
            {
                "title": panel.get("title") or "Need help?",
                "description": panel.get("description")
                or "Click the button below to open a private support ticket.",
                "color": 0x5865F2,
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": str(panel.get("button_label") or "Open Ticket")[
                            :80
                        ],
                        "emoji": {"name": "🎫"},
                        "custom_id": OPEN_BUTTON_ID,
                    }
                ],
            }
        ],
    }

    auth_headers = {"Authorization": f"Bot {bot_token}"}
    existing_message_id = str(panel.get("message_id") or "").strip() or None

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = None

        if existing_message_id:
            try:
                edit_response = await client.patch(
                    (
                        f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                        f"/messages/{existing_message_id}"
                    ),
                    headers=auth_headers,
                    json=message_payload,
                )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not reach Discord: {error}",
                ) from error

            if edit_response.status_code == 200:
                response = edit_response
            elif edit_response.status_code == 404:
                existing_message_id = None
            else:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Discord rejected the panel edit "
                        f"(HTTP {edit_response.status_code}): "
                        f"{edit_response.text[:200]}"
                    ),
                )

        if response is None:
            try:
                response = await client.post(
                    f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages",
                    headers=auth_headers,
                    json=message_payload,
                )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not reach Discord: {error}",
                ) from error

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Discord rejected the panel message "
                        f"(HTTP {response.status_code}): {response.text[:200]}"
                    ),
                )

    message_body = response.json()
    panel["message_id"] = str(message_body.get("id") or "") or None
    panel["published_at"] = now_iso()

    await write_ticket_panels(guild_id, panels)

    return {
        "ok": True,
        "channel_id": channel_id,
        "message_id": panel.get("message_id"),
        "published_at": panel["published_at"],
    }
