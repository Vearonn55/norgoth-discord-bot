"""Guild-scoped reusable Discord embed messages: CRUD, send, and edit-sync."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_database_session
from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.models.embed_messages import EmbedMessage, EmbedMessageDelivery
from app.services.discord.embed_builder import build_embed_dict

logger = logging.getLogger("norgoth.embed_messages")

router = APIRouter(
    tags=["Embed Messages"],
    dependencies=[Depends(guild_manager_dependency())],
)


async def require_bot_token(
    x_norgoth_bot_token: str | None = Header(default=None),
) -> None:
    """Guard internal endpoints the bot calls (no OAuth available to it).

    The bot and API load the same ``DISCORD_BOT_TOKEN`` from the environment, so
    a matching header proves the caller is our bot process.
    """

    settings = get_settings()
    expected = settings.discord_bot_token
    if not expected or x_norgoth_bot_token != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token.")


# Internal, bot-only router for live drift callbacks (message deletions).
internal_router = APIRouter(
    tags=["Embed Messages (internal)"],
    dependencies=[Depends(require_bot_token)],
)

SNOWFLAKE = r"^[0-9]{5,25}$"


class EmbedMessageBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=2000)
    embed_json: Optional[dict[str, Any]] = None
    target_channel_ids: list[str] = Field(default_factory=list, max_length=25)


class SendRequest(BaseModel):
    channel_id: str = Field(pattern=SNOWFLAKE)


class DeleteRequest(BaseModel):
    delete_discord_messages: bool = False


_SNOWFLAKE_RE = re.compile(r"^[0-9]{5,25}$")


def _clean_channel_ids(channel_ids: list[str]) -> list[str]:
    """De-duplicate + validate target channel IDs, preserving order."""

    seen: set[str] = set()
    cleaned: list[str] = []
    for channel_id in channel_ids:
        candidate = str(channel_id).strip()
        if _SNOWFLAKE_RE.match(candidate) and candidate not in seen:
            seen.add(candidate)
            cleaned.append(candidate)
    return cleaned[:25]


def _delivery_is_live(delivery: EmbedMessageDelivery) -> bool:
    """A delivery represents a message currently present in Discord."""

    return bool(delivery.discord_message_id) and delivery.status == "synced"


def _serialize_delivery(
    delivery: EmbedMessageDelivery,
    message_version: int,
) -> dict[str, Any]:
    stale = _delivery_is_live(delivery) and (
        (delivery.deployed_version or 0) < message_version
    )
    return {
        "id": str(delivery.id),
        "channel_id": delivery.channel_id,
        "discord_message_id": delivery.discord_message_id,
        "delivery_type": delivery.delivery_type,
        "status": delivery.status,
        "error": delivery.error,
        "deployed_version": delivery.deployed_version,
        "stale": stale,
        "last_synced_at": (
            delivery.last_synced_at.isoformat() if delivery.last_synced_at else None
        ),
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
    }


def _serialize(message: EmbedMessage) -> dict[str, Any]:
    version = message.version or 1
    deliveries = list(message.deliveries or [])
    targets = message.target_channel_ids or []

    # A copy is "live" when present + synced. Sync state counts live copies
    # among configured target channels.
    live_channels = {d.channel_id for d in deliveries if _delivery_is_live(d)}
    synced_targets = sum(1 for ch in targets if ch in live_channels)
    has_published = any(d.discord_message_id for d in deliveries)
    needs_resync = any(
        _delivery_is_live(d) and (d.deployed_version or 0) < version
        for d in deliveries
    )

    return {
        "id": str(message.id),
        "guild_id": message.guild_id,
        "name": message.name,
        "description": message.description,
        "content": message.content,
        "embed_json": message.embed_json,
        "target_channel_ids": targets,
        "version": version,
        "created_by": message.created_by,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
        "has_published": has_published,
        "synced_count": synced_targets,
        "target_count": len(targets),
        "needs_resync": needs_resync,
        "deliveries": [
            _serialize_delivery(delivery, version) for delivery in deliveries
        ],
    }


async def _load_message(
    session: AsyncSession,
    guild_id: str,
    message_id: UUID,
) -> EmbedMessage:
    result = await session.scalar(
        select(EmbedMessage)
        .where(EmbedMessage.id == message_id, EmbedMessage.guild_id == guild_id)
        .options(selectinload(EmbedMessage.deliveries))
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Embed message not found.")
    return result


@router.get("/guilds/{guild_id}/embed-messages")
async def list_embed_messages(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(EmbedMessage)
        .where(EmbedMessage.guild_id == guild_id)
        .options(selectinload(EmbedMessage.deliveries))
        .order_by(EmbedMessage.updated_at.desc())
    )
    return [_serialize(row) for row in rows]


@router.post("/guilds/{guild_id}/embed-messages")
async def create_embed_message(
    body: EmbedMessageBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = EmbedMessage(
        guild_id=guild_id,
        name=body.name,
        description=body.description,
        content=body.content,
        embed_json=body.embed_json,
        target_channel_ids=_clean_channel_ids(body.target_channel_ids),
    )
    session.add(message)
    await session.commit()
    # Reload with the deliveries relationship eagerly loaded. Assigning the
    # collection directly after refresh() triggers an implicit lazy-load on the
    # async session (MissingGreenlet) which surfaced as a 500 on create.
    message = await _load_message(session, guild_id, message.id)
    return _serialize(message)


@router.get("/guilds/{guild_id}/embed-messages/{message_id}")
async def get_embed_message(
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = await _load_message(session, guild_id, message_id)
    return _serialize(message)


@router.put("/guilds/{guild_id}/embed-messages/{message_id}")
async def update_embed_message(
    body: EmbedMessageBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = await _load_message(session, guild_id, message_id)

    cleaned_targets = _clean_channel_ids(body.target_channel_ids)
    # Bump the desired revision only when something publishable changed so
    # already-deployed copies are flagged stale (needs re-sync). Name/description
    # are metadata only and do not affect the posted message.
    publishable_changed = (
        message.content != body.content
        or message.embed_json != body.embed_json
        or (message.target_channel_ids or []) != cleaned_targets
    )

    message.name = body.name
    message.description = body.description
    message.content = body.content
    message.embed_json = body.embed_json
    message.target_channel_ids = cleaned_targets
    if publishable_changed:
        message.version = (message.version or 1) + 1

    await session.commit()
    await session.refresh(message)
    message = await _load_message(session, guild_id, message_id)
    return _serialize(message)


@router.delete("/guilds/{guild_id}/embed-messages/{message_id}")
async def delete_embed_message(
    body: DeleteRequest | None = None,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = await _load_message(session, guild_id, message_id)

    delete_discord = bool(body and body.delete_discord_messages)
    discord_deleted = 0
    discord_failed = 0

    if delete_discord:
        settings = get_settings()
        if not settings.discord_bot_token:
            raise HTTPException(
                status_code=503, detail="Discord bot token not configured."
            )
        editable = [
            delivery
            for delivery in message.deliveries
            if delivery.discord_message_id and delivery.delivery_type == "bot"
        ]
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            for delivery in editable:
                try:
                    await bot.delete_channel_message(
                        delivery.channel_id,
                        str(delivery.discord_message_id),
                        reason="Norgoth embed template deleted",
                    )
                    discord_deleted += 1
                except DiscordBotAPIError:
                    discord_failed += 1

    # Deleting the template removes the reusable config + delivery records
    # (cascade). Discord messages are only removed when explicitly requested.
    await session.delete(message)
    await session.commit()
    return {
        "ok": True,
        "deleted_id": str(message_id),
        "discord_deleted": discord_deleted,
        "discord_failed": discord_failed,
    }


def _build_payload(message: EmbedMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    content = (message.content or "").strip()
    if content:
        payload["content"] = content[:2000]
    embed = build_embed_dict(message.embed_json)
    if embed:
        payload["embeds"] = [embed]
    if not payload:
        # Discord rejects fully empty messages; fall back to the name.
        payload["content"] = message.name[:2000]
    return payload


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/send")
async def send_embed_message(
    body: SendRequest,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    message = await _load_message(session, guild_id, message_id)
    payload = _build_payload(message)

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        try:
            sent = await bot.send_channel_message(body.channel_id, payload)
        except DiscordBotAPIError as error:
            status = _status_for_error(error)
            delivery = EmbedMessageDelivery(
                embed_message_id=message.id,
                guild_id=guild_id,
                channel_id=body.channel_id,
                delivery_type="bot",
                status=status,
                error=str(error),
            )
            session.add(delivery)
            await session.commit()
            raise HTTPException(
                status_code=502,
                detail=f"Discord rejected the message: {error}",
            ) from error

    delivery = EmbedMessageDelivery(
        embed_message_id=message.id,
        guild_id=guild_id,
        channel_id=body.channel_id,
        discord_message_id=str(sent.get("id") or "") or None,
        delivery_type="bot",
        status="synced",
        deployed_version=message.version,
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(delivery)
    await session.commit()

    message = await _load_message(session, guild_id, message_id)
    return _serialize(message)


def _status_for_error(error: DiscordBotAPIError) -> str:
    if error.status_code == 404:
        return "message_missing"
    if error.status_code == 403:
        return "permission_missing"
    return "error"


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/sync")
async def sync_embed_message(
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Re-apply the current embed to every previously-sent Discord message.

    Failures are recorded per-delivery and do not abort the whole sync.
    """
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    message = await _load_message(session, guild_id, message_id)
    payload = _build_payload(message)

    editable = [
        delivery
        for delivery in message.deliveries
        if delivery.discord_message_id and delivery.delivery_type == "bot"
    ]

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        for delivery in editable:
            try:
                await bot.edit_channel_message(
                    delivery.channel_id,
                    str(delivery.discord_message_id),
                    payload,
                )
                delivery.status = "synced"
                delivery.error = None
                delivery.deployed_version = message.version
                delivery.last_synced_at = datetime.now(timezone.utc)
            except DiscordBotAPIError as error:
                delivery.status = _status_for_error(error)
                delivery.error = str(error)

    await session.commit()
    message = await _load_message(session, guild_id, message_id)
    return _serialize(message)


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/resync")
async def resync_embed_message(
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Reconcile every target channel to the current embed.

    Unlike /sync (edit-only), Re-Sync restores drift: live copies are edited in
    place, while missing copies (never sent, externally deleted, or 404 on edit)
    are re-sent. This brings a 2/3 state back to 3/3 without duplicating the
    healthy copies.
    """
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    message = await _load_message(session, guild_id, message_id)
    targets = message.target_channel_ids or []
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No target channels configured. Add channels and save first.",
        )

    payload = _build_payload(message)
    deliveries_by_channel: dict[str, EmbedMessageDelivery] = {
        delivery.channel_id: delivery
        for delivery in message.deliveries
        if delivery.delivery_type == "bot"
    }

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        for channel_id in targets:
            existing = deliveries_by_channel.get(channel_id)
            # A copy is editable only when we believe it still exists.
            can_edit = bool(
                existing
                and existing.discord_message_id
                and existing.status == "synced"
            )
            try:
                if can_edit and existing is not None:
                    try:
                        await bot.edit_channel_message(
                            channel_id,
                            str(existing.discord_message_id),
                            payload,
                        )
                        existing.status = "synced"
                        existing.error = None
                        existing.deployed_version = message.version
                        existing.last_synced_at = datetime.now(timezone.utc)
                        results.append({"channel_id": channel_id, "status": "synced"})
                        continue
                    except DiscordBotAPIError as edit_error:
                        # The copy vanished between checks — fall through to resend.
                        if edit_error.status_code != 404:
                            raise
                # Missing copy: (re)send a fresh message.
                sent = await bot.send_channel_message(channel_id, payload)
                new_id = str(sent.get("id") or "") or None
                if existing is not None:
                    existing.discord_message_id = new_id
                    existing.status = "synced"
                    existing.error = None
                    existing.deployed_version = message.version
                    existing.last_synced_at = datetime.now(timezone.utc)
                else:
                    session.add(
                        EmbedMessageDelivery(
                            embed_message_id=message.id,
                            guild_id=guild_id,
                            channel_id=channel_id,
                            discord_message_id=new_id,
                            delivery_type="bot",
                            status="synced",
                            deployed_version=message.version,
                            last_synced_at=datetime.now(timezone.utc),
                        )
                    )
                results.append({"channel_id": channel_id, "status": "sent"})
            except DiscordBotAPIError as error:
                status = _status_for_error(error)
                if existing is not None:
                    existing.status = status
                    existing.error = str(error)
                else:
                    session.add(
                        EmbedMessageDelivery(
                            embed_message_id=message.id,
                            guild_id=guild_id,
                            channel_id=channel_id,
                            delivery_type="bot",
                            status=status,
                            error=str(error),
                        )
                    )
                results.append(
                    {"channel_id": channel_id, "status": status, "error": str(error)}
                )

    await session.commit()
    message = await _load_message(session, guild_id, message_id)
    return {**_serialize(message), "results": results}


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/publish")
async def publish_embed_message(
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Publish the embed to every configured target channel.

    Channels already delivered are edited in place; new channels get a fresh
    message. Per-channel failures are recorded and do not abort the batch.
    """
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    message = await _load_message(session, guild_id, message_id)
    targets = message.target_channel_ids or []
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No target channels configured. Add channels and save first.",
        )

    payload = _build_payload(message)
    deliveries_by_channel: dict[str, EmbedMessageDelivery] = {
        delivery.channel_id: delivery
        for delivery in message.deliveries
        if delivery.delivery_type == "bot"
    }

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        for channel_id in targets:
            existing = deliveries_by_channel.get(channel_id)
            try:
                if existing and existing.discord_message_id:
                    await bot.edit_channel_message(
                        channel_id,
                        str(existing.discord_message_id),
                        payload,
                    )
                    existing.status = "synced"
                    existing.error = None
                    existing.deployed_version = message.version
                    existing.last_synced_at = datetime.now(timezone.utc)
                    results.append({"channel_id": channel_id, "status": "synced"})
                else:
                    sent = await bot.send_channel_message(channel_id, payload)
                    if existing:
                        existing.discord_message_id = (
                            str(sent.get("id") or "") or None
                        )
                        existing.status = "synced"
                        existing.error = None
                        existing.deployed_version = message.version
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        session.add(
                            EmbedMessageDelivery(
                                embed_message_id=message.id,
                                guild_id=guild_id,
                                channel_id=channel_id,
                                discord_message_id=str(sent.get("id") or "")
                                or None,
                                delivery_type="bot",
                                status="synced",
                                deployed_version=message.version,
                                last_synced_at=datetime.now(timezone.utc),
                            )
                        )
                    results.append({"channel_id": channel_id, "status": "sent"})
            except DiscordBotAPIError as error:
                status = _status_for_error(error)
                if existing:
                    existing.status = status
                    existing.error = str(error)
                else:
                    session.add(
                        EmbedMessageDelivery(
                            embed_message_id=message.id,
                            guild_id=guild_id,
                            channel_id=channel_id,
                            delivery_type="bot",
                            status=status,
                            error=str(error),
                        )
                    )
                results.append(
                    {
                        "channel_id": channel_id,
                        "status": status,
                        "error": str(error),
                    }
                )

    await session.commit()
    message = await _load_message(session, guild_id, message_id)
    return {**_serialize(message), "results": results}


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/reconcile")
async def reconcile_embed_message(
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Probe Discord for each tracked delivery and refresh its status.

    This performs no edits or sends — it only detects drift (e.g. a message an
    admin deleted in Discord) so the dashboard can show an accurate sync state
    (3/3 → 2/3) on demand, without waiting for the bot's live listeners.
    """
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    message = await _load_message(session, guild_id, message_id)

    probed = 0
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        for delivery in message.deliveries:
            if delivery.delivery_type != "bot" or not delivery.discord_message_id:
                continue
            probed += 1
            try:
                await bot.get_channel_message(
                    delivery.channel_id,
                    str(delivery.discord_message_id),
                )
                # Still present. Leave status alone unless it was flagged missing.
                if delivery.status == "message_missing":
                    delivery.status = "synced"
                    delivery.error = None
            except DiscordBotAPIError as error:
                if error.status_code == 404:
                    delivery.status = "message_missing"
                    delivery.error = "Message no longer exists in Discord."
                elif error.status_code == 403:
                    delivery.status = "permission_missing"
                    delivery.error = str(error)

    await session.commit()
    message = await _load_message(session, guild_id, message_id)
    return {**_serialize(message), "probed": probed}


class MarkDeletedRequest(BaseModel):
    message_ids: list[str] = Field(default_factory=list, max_length=200)


@internal_router.post("/internal/embed-deliveries/mark-deleted")
async def mark_deliveries_deleted(
    body: MarkDeletedRequest,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Flag deliveries whose Discord message was deleted (bot-driven drift).

    Called by the bot's raw-delete listeners so an externally deleted embed
    copy flips to ``message_missing`` (3/3 → 2/3) without on-demand polling.
    """

    ids = [str(mid).strip() for mid in body.message_ids if str(mid).strip()]
    if not ids:
        return {"updated": 0}

    rows = await session.scalars(
        select(EmbedMessageDelivery).where(
            EmbedMessageDelivery.discord_message_id.in_(ids)
        )
    )
    updated = 0
    for delivery in rows:
        if delivery.status != "message_missing":
            delivery.status = "message_missing"
            delivery.error = "Message deleted in Discord."
            updated += 1

    if updated:
        await session.commit()
    return {"updated": updated}
