"""Guild-scoped reusable Discord embed messages: CRUD, send, and edit-sync."""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_database_session
from app.services.campaign_store import get_redis
from app.security.internal_auth import require_internal_token
from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.models.embed_messages import (
    EmbedMessage,
    EmbedMessageDelivery,
)
from app.routes.role_menus import (
    reapply_menu_components_for_deliveries,
    read_menus,
)
from app.core.content_limits import MAX_STORED_MARKDOWN_CHARS
from app.services.discord.message_compiler import compile_discord_messages
from app.services.feature_config_store import load_config
from app.services.snapshot_writer import delete_snapshot, write_snapshot

logger = logging.getLogger("norgoth.embed_messages")

router = APIRouter(
    tags=["Embed Messages"],
    dependencies=[Depends(guild_manager_dependency())],
)


# Internal, bot-only router for live drift callbacks (message deletions).
internal_router = APIRouter(
    tags=["Embed Messages (internal)"],
    dependencies=[Depends(require_internal_token)],
)

SNOWFLAKE = r"^[0-9]{5,25}$"
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class EmbedMessageBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=MAX_STORED_MARKDOWN_CHARS)
    embed_json: Optional[dict[str, Any]] = None

    @field_validator("embed_json")
    @classmethod
    def _cap_embed_markdown(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return value
        description = value.get("description")
        if isinstance(description, str) and len(description) > MAX_STORED_MARKDOWN_CHARS:
            raise ValueError(
                f"Embed description must be {MAX_STORED_MARKDOWN_CHARS} characters or fewer."
            )
        return value


class SendRequest(BaseModel):
    channel_id: str = Field(pattern=SNOWFLAKE)


class DeleteRequest(BaseModel):
    delete_discord_messages: bool = False
    # Bypass the dependency guard when a draft is still referenced by a feature
    # (role menu / welcome-leave). Callers must confirm intent explicitly.
    force: bool = False


# Ownership marker for deployments the Embed Library itself created and may
# freely recreate; feature-owned deployments are handled by their feature.
OWNER_LIBRARY = "embed_library"
OWNER_SAR = "self_assignable_role"
RESYNC_LOCK_TTL_SECONDS = 30


def _delivery_is_live(delivery: EmbedMessageDelivery) -> bool:
    """A delivery represents a message currently present in Discord."""

    return bool(delivery.discord_message_id) and delivery.status == "synced"


_ERROR_STATUSES = {
    "error",
    "channel_missing",
    "permission_missing",
    "webhook_missing",
}


async def _sar_delivery_ids(guild_id: str) -> set[str]:
    """Return delivery ids currently bound by Self-Assignable Role menus.

    Runtime binding is authoritative for ownership: any delivery a role menu
    points at is treated as SAR-owned regardless of the stored ``owner_feature``
    column, so generic Re-Sync never recreates it as a plain (component-less)
    embed.
    """

    try:
        menus = await read_menus(guild_id)
    except Exception:  # pragma: no cover - defensive: Redis/config unavailable
        return set()
    bound: set[str] = set()
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        if (menu.get("binding_type") or "standalone") != "embed_message":
            continue
        delivery_id = str(menu.get("embed_delivery_id") or "").strip()
        if delivery_id:
            bound.add(delivery_id)
    return bound


def _effective_owner(
    delivery: EmbedMessageDelivery,
    sar_delivery_ids: set[str],
) -> str:
    """Resolve which feature owns a deployment (runtime SAR binding wins)."""

    if str(delivery.id) in sar_delivery_ids or delivery.owner_feature == OWNER_SAR:
        return OWNER_SAR
    return delivery.owner_feature or OWNER_LIBRARY


def _delivery_state(
    delivery: EmbedMessageDelivery,
    message_version: int,
    owner: str,
) -> str:
    """Per-deployment reconciliation state used by the dashboard.

    pending | synced | out_of_date | missing | needs_feature_repair | error
    """

    if delivery.status == "pending":
        return "pending"
    if delivery.status in _ERROR_STATUSES:
        return "error"
    if delivery.status == "message_missing" or not delivery.discord_message_id:
        # A component-bound (SAR) message cannot be safely recreated as a plain
        # embed by the library — the owning feature must repair it.
        return "needs_feature_repair" if owner == OWNER_SAR else "missing"
    if (delivery.deployed_version or 0) < message_version:
        return "out_of_date"
    return "synced"


def _serialize_delivery(
    delivery: EmbedMessageDelivery,
    message_version: int,
    owner: str,
    state: str,
) -> dict[str, Any]:
    created_iso = delivery.created_at.isoformat() if delivery.created_at else None
    return {
        "id": str(delivery.id),
        "channel_id": delivery.channel_id,
        "discord_message_id": delivery.discord_message_id,
        "discord_message_ids": _delivery_message_ids(delivery) or None,
        "delivery_type": delivery.delivery_type,
        "status": delivery.status,
        "state": state,
        "owner_feature": owner,
        "error": delivery.error,
        "deployed_version": delivery.deployed_version,
        "stale": state == "out_of_date",
        "last_synced_at": (
            delivery.last_synced_at.isoformat() if delivery.last_synced_at else None
        ),
        "created_at": created_iso,
        # Publication timestamp of this specific instance. Each delivery is an
        # independently selectable published instance (e.g. for Self-Assignable
        # Roles), so we surface when it first went live.
        "published_at": created_iso,
    }


# Worst-first precedence for rolling per-deployment states into one draft status.
_STATE_PRECEDENCE = [
    "error",
    "pending",
    "missing",
    "needs_feature_repair",
    "out_of_date",
    "synced",
]


def _serialize(
    message: EmbedMessage,
    sar_delivery_ids: set[str] | None = None,
) -> dict[str, Any]:
    version = message.version or 1
    deliveries = list(message.deliveries or [])
    sar_ids = sar_delivery_ids or set()

    serialized_deliveries: list[dict[str, Any]] = []
    states: list[str] = []
    for delivery in deliveries:
        owner = _effective_owner(delivery, sar_ids)
        state = _delivery_state(delivery, version, owner)
        states.append(state)
        serialized_deliveries.append(
            _serialize_delivery(delivery, version, owner, state)
        )

    deployment_count = len(deliveries)
    synced_count = sum(1 for s in states if s == "synced")
    has_published = any(d.discord_message_id for d in deliveries)
    needs_resync = any(s in {"out_of_date", "missing"} for s in states)

    if deployment_count == 0:
        sync_status = "draft_only"
    else:
        sync_status = "synced"
        state_set = set(states)
        for candidate in _STATE_PRECEDENCE:
            if candidate in state_set:
                sync_status = candidate
                break

    return {
        "id": str(message.id),
        "guild_id": message.guild_id,
        "name": message.name,
        "description": message.description,
        "content": message.content,
        "embed_json": message.embed_json,
        "version": version,
        "created_by": message.created_by,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
        "has_published": has_published,
        "deployment_count": deployment_count,
        "synced_count": synced_count,
        # ``current_count`` retained as an alias of synced_count for any legacy
        # reader; both count fully-synced live deployments.
        "current_count": synced_count,
        "needs_resync": needs_resync,
        "sync_status": sync_status,
        "deliveries": serialized_deliveries,
    }


def embed_draft_suffix(message_id: UUID | str) -> str:
    """Redis snapshot suffix for a single embed draft the bot can render."""

    return f"embeds:draft:{message_id}"


async def _write_embed_draft_snapshot(message: EmbedMessage) -> None:
    """Publish a draft snapshot the bot reads to render referenced embeds.

    Features like Welcome/Leave reference an embed draft by id; the bot renders
    it at delivery time (with variable substitution) from this snapshot rather
    than calling the API on the hot path.
    """

    await write_snapshot(
        message.guild_id,
        embed_draft_suffix(message.id),
        {
            "id": str(message.id),
            "name": message.name,
            "content": message.content or "",
            "embed_json": message.embed_json,
            "version": message.version or 1,
        },
    )


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
    sar_ids = await _sar_delivery_ids(guild_id)
    return [_serialize(row, sar_ids) for row in rows]


@router.post("/guilds/{guild_id}/embed-messages")
async def create_embed_message(
    body: EmbedMessageBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    # Drafts are content-only; deployment channels are chosen by the Deploy
    # action or by consuming features, never stored on the draft.
    message = EmbedMessage(
        guild_id=guild_id,
        name=body.name,
        description=body.description,
        content=body.content,
        embed_json=body.embed_json,
    )
    session.add(message)
    await session.commit()
    # Reload with the deliveries relationship eagerly loaded. Assigning the
    # collection directly after refresh() triggers an implicit lazy-load on the
    # async session (MissingGreenlet) which surfaced as a 500 on create.
    message = await _load_message(session, guild_id, message.id)
    await _write_embed_draft_snapshot(message)
    return _serialize(message, await _sar_delivery_ids(guild_id))


@router.get("/guilds/{guild_id}/embed-messages/{message_id}")
async def get_embed_message(
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = await _load_message(session, guild_id, message_id)
    return _serialize(message, await _sar_delivery_ids(guild_id))


@router.put("/guilds/{guild_id}/embed-messages/{message_id}")
async def update_embed_message(
    body: EmbedMessageBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = await _load_message(session, guild_id, message_id)

    # Bump the desired revision only when publishable content changed so
    # already-deployed copies are flagged stale (needs re-sync). Name/description
    # are metadata only and do not affect the posted message.
    publishable_changed = (
        message.content != body.content or message.embed_json != body.embed_json
    )

    message.name = body.name
    message.description = body.description
    message.content = body.content
    message.embed_json = body.embed_json
    if publishable_changed:
        message.version = (message.version or 1) + 1

    await session.commit()
    await session.refresh(message)
    message = await _load_message(session, guild_id, message_id)
    await _write_embed_draft_snapshot(message)
    return _serialize(message, await _sar_delivery_ids(guild_id))


async def _draft_dependencies(
    guild_id: str,
    message: EmbedMessage,
) -> list[dict[str, str]]:
    """Return features that reference this draft (block delete unless forced).

    A draft may be consumed by Self-Assignable Role menus (bound to one of its
    deliveries) or by Welcome/Leave messages (referenced by draft id). Deleting
    it would orphan those features, so surface them for an explicit warning.
    """

    deps: list[dict[str, str]] = []
    message_id = str(message.id)
    delivery_ids = {str(d.id) for d in message.deliveries}

    try:
        menus = await read_menus(guild_id)
    except Exception:  # pragma: no cover - defensive
        menus = []
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        bound_delivery = str(menu.get("embed_delivery_id") or "").strip()
        bound_message = str(menu.get("embed_message_id") or "").strip()
        if bound_delivery in delivery_ids or bound_message == message_id:
            deps.append(
                {
                    "feature": "self_assignable_role",
                    "label": str(menu.get("name") or menu.get("id") or "Role menu"),
                }
            )

    try:
        automation = await load_config(guild_id, "automation")
    except Exception:  # pragma: no cover - defensive
        automation = None
    if isinstance(automation, dict):
        if str(automation.get("welcome_embed_message_id") or "") == message_id:
            deps.append({"feature": "welcome", "label": "Welcome message"})
        if str(automation.get("leave_embed_message_id") or "") == message_id:
            deps.append({"feature": "leave", "label": "Leave message"})

    try:
        from app.routes.tickets import read_ticket_panels

        panels = await read_ticket_panels(guild_id)
    except Exception:  # pragma: no cover - defensive
        panels = []
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        if str(panel.get("embed_message_id") or "").strip() == message_id:
            deps.append(
                {
                    "feature": "tickets",
                    "label": str(panel.get("name") or panel.get("id") or "Ticket panel"),
                }
            )

    return deps


@router.delete("/guilds/{guild_id}/embed-messages/{message_id}")
async def delete_embed_message(
    body: DeleteRequest | None = None,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    message = await _load_message(session, guild_id, message_id)

    force = bool(body and body.force)
    if not force:
        dependencies = await _draft_dependencies(guild_id, message)
        if dependencies:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "This embed draft is still used by other features. "
                        "Detach them or delete with force=true."
                    ),
                    "dependencies": dependencies,
                },
            )

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
            if _delivery_message_ids(delivery) and delivery.delivery_type == "bot"
        ]
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            for delivery in editable:
                for discord_id in _delivery_message_ids(delivery):
                    try:
                        await bot.delete_channel_message(
                            delivery.channel_id,
                            discord_id,
                            reason="Norgoth embed template deleted",
                        )
                        discord_deleted += 1
                    except DiscordBotAPIError:
                        discord_failed += 1

    # Deleting the template removes the reusable config + delivery records
    # (cascade). Discord messages are only removed when explicitly requested.
    await session.delete(message)
    await session.commit()
    await delete_snapshot(guild_id, embed_draft_suffix(message_id))
    return {
        "ok": True,
        "deleted_id": str(message_id),
        "discord_deleted": discord_deleted,
        "discord_failed": discord_failed,
    }


def _build_payload(message: EmbedMessage) -> dict[str, Any]:
    compiled = compile_discord_messages(
        content=message.content,
        embed_json=message.embed_json,
        fallback_name=message.name,
    )
    if not compiled.ok:
        error = compiled.errors[0]
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.message},
        )
    return compiled.payloads[0]


def _build_payloads(message: EmbedMessage) -> list[dict[str, Any]]:
    compiled = compile_discord_messages(
        content=message.content,
        embed_json=message.embed_json,
        fallback_name=message.name,
    )
    if not compiled.ok:
        error = compiled.errors[0]
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.message},
        )
    return compiled.payloads


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/send")
async def send_embed_message(
    body: SendRequest,
    request: Request,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    started = time.perf_counter()
    request_id = getattr(request.state, "request_id", "unavailable")
    key = _normalize_idempotency_key(idempotency_key)
    validation_code: str | None = None
    discord_status: int | str | None = None
    persist_ok = False
    payload_count = 0
    embed_count = 0

    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "bot_missing",
                "message": "Discord bot token not configured.",
            },
        )

    message = await _load_message(session, guild_id, message_id)
    existing = _find_delivery_by_key(message, body.channel_id, key)
    if existing is not None:
        if _delivery_message_ids(existing):
            if existing.status != "synced":
                existing.status = "synced"
                existing.error = None
                existing.deployed_version = message.version
                existing.last_synced_at = datetime.now(timezone.utc)
                await session.commit()
            persist_ok = True
            _log_embed_deploy(
                request_id=str(request_id),
                guild_id=guild_id,
                message_id=str(message_id),
                embed_count=embed_count,
                payload_count=payload_count,
                validation_code=validation_code,
                discord_status=discord_status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                idempotency_key=key,
                persist_ok=persist_ok,
            )
            message = await _load_message(session, guild_id, message_id)
            return _serialize(message, await _sar_delivery_ids(guild_id))
        if existing.status == "pending":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "deploy_in_progress",
                    "message": "A deploy with this key is already in progress.",
                },
            )

    try:
        payloads = _build_payloads(message)
    except HTTPException as error:
        structured = error.detail if isinstance(error.detail, dict) else None
        if isinstance(structured, dict) and isinstance(structured.get("code"), str):
            validation_code = structured["code"]
        _log_embed_deploy(
            request_id=str(request_id),
            guild_id=guild_id,
            message_id=str(message_id),
            embed_count=0,
            payload_count=0,
            validation_code=validation_code,
            discord_status=None,
            duration_ms=int((time.perf_counter() - started) * 1000),
            idempotency_key=key,
            persist_ok=False,
        )
        raise

    payload_count = len(payloads)
    embed_count = sum(len(payload.get("embeds") or []) for payload in payloads)

    delivery = existing
    if delivery is None:
        delivery = EmbedMessageDelivery(
            embed_message_id=message.id,
            guild_id=guild_id,
            channel_id=body.channel_id,
            delivery_type="bot",
            owner_feature=OWNER_LIBRARY,
            status="pending",
            idempotency_key=key,
        )
        session.add(delivery)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            message = await _load_message(session, guild_id, message_id)
            raced = _find_delivery_by_key(message, body.channel_id, key)
            if raced is not None and _delivery_message_ids(raced):
                persist_ok = True
                _log_embed_deploy(
                    request_id=str(request_id),
                    guild_id=guild_id,
                    message_id=str(message_id),
                    embed_count=embed_count,
                    payload_count=payload_count,
                    validation_code=validation_code,
                    discord_status=discord_status,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    idempotency_key=key,
                    persist_ok=persist_ok,
                )
                return _serialize(message, await _sar_delivery_ids(guild_id))
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "deploy_in_progress",
                    "message": "A deploy with this key is already in progress.",
                },
            ) from None
        await session.commit()
        await session.refresh(delivery)
    else:
        delivery.status = "pending"
        delivery.error = None
        await session.commit()

    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            sent_ids = await _post_payloads(bot, body.channel_id, payloads)
        _apply_sent_ids(delivery, sent_ids)
        delivery.status = "synced"
        delivery.error = None
        delivery.deployed_version = message.version
        delivery.last_synced_at = datetime.now(timezone.utc)
        await session.commit()
        persist_ok = True
    except DiscordBotAPIError as error:
        discord_status = error.status_code
        delivery.status = _status_for_error(error)
        delivery.error = _safe_discord_error(error)
        await session.commit()
        _log_embed_deploy(
            request_id=str(request_id),
            guild_id=guild_id,
            message_id=str(message_id),
            embed_count=embed_count,
            payload_count=payload_count,
            validation_code=validation_code,
            discord_status=discord_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            idempotency_key=key,
            persist_ok=False,
        )
        raise _http_exception_for_discord_error(error) from error
    except httpx.TimeoutException as error:
        discord_status = "timeout"
        delivery.status = "error"
        delivery.error = "timeout"
        await session.commit()
        _log_embed_deploy(
            request_id=str(request_id),
            guild_id=guild_id,
            message_id=str(message_id),
            embed_count=embed_count,
            payload_count=payload_count,
            validation_code=validation_code,
            discord_status=discord_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            idempotency_key=key,
            persist_ok=False,
        )
        raise HTTPException(
            status_code=504,
            detail={
                "code": "timeout",
                "message": "Discord did not respond in time.",
            },
        ) from error

    _log_embed_deploy(
        request_id=str(request_id),
        guild_id=guild_id,
        message_id=str(message_id),
        embed_count=embed_count,
        payload_count=payload_count,
        validation_code=validation_code,
        discord_status=discord_status,
        duration_ms=int((time.perf_counter() - started) * 1000),
        idempotency_key=key,
        persist_ok=persist_ok,
    )
    message = await _load_message(session, guild_id, message_id)
    return _serialize(message, await _sar_delivery_ids(guild_id))


def _changed_deliveries(
    message: EmbedMessage,
    prior_message_ids: dict[str, str | None],
) -> dict[str, tuple[str, str]]:
    """Map delivery_id → (channel_id, message_id) for re-sent instances.

    Includes deliveries whose Discord message id changed (new send) or that are
    newly created. Used to re-apply role-menu controls bound to those instances.
    """

    changed: dict[str, tuple[str, str]] = {}
    for delivery in message.deliveries:
        if not delivery.discord_message_id:
            continue
        key = str(delivery.id)
        if prior_message_ids.get(key) != delivery.discord_message_id:
            changed[key] = (delivery.channel_id, str(delivery.discord_message_id))
    return changed


def _status_for_error(error: DiscordBotAPIError) -> str:
    if error.status_code == 404:
        return "message_missing"
    if error.status_code == 403:
        return "permission_missing"
    return "error"


def _normalize_idempotency_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if _IDEMPOTENCY_KEY.fullmatch(value) is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_payload",
                "message": "Idempotency-Key must be 8–64 URL-safe characters.",
            },
        )
    return value


def _find_delivery_by_key(
    message: EmbedMessage,
    channel_id: str,
    key: str | None,
) -> EmbedMessageDelivery | None:
    if not key:
        return None
    for delivery in message.deliveries or []:
        if delivery.channel_id == channel_id and delivery.idempotency_key == key:
            return delivery
    return None


def _delivery_message_ids(delivery: EmbedMessageDelivery) -> list[str]:
    ids: list[str] = []
    raw = getattr(delivery, "discord_message_ids", None)
    if isinstance(raw, list):
        ids.extend(str(item) for item in raw if item)
    primary = getattr(delivery, "discord_message_id", None)
    if primary and str(primary) not in ids:
        ids.insert(0, str(primary))
    return ids


def _apply_sent_ids(delivery: EmbedMessageDelivery, ids: list[str]) -> None:
    cleaned = [item for item in ids if item]
    delivery.discord_message_ids = cleaned or None
    delivery.discord_message_id = cleaned[0] if cleaned else None


async def _post_payloads(
    bot: DiscordBotClient,
    channel_id: str,
    payloads: list[dict[str, Any]],
) -> list[str]:
    sent_ids: list[str] = []
    for payload in payloads:
        sent = await bot.send_channel_message(channel_id, payload)
        message_id = str(sent.get("id") or "")
        if message_id:
            sent_ids.append(message_id)
    return sent_ids


def _safe_discord_error(error: DiscordBotAPIError) -> str:
    status = error.status_code if error.status_code is not None else "timeout"
    code = getattr(error, "discord_code", None)
    if code is not None:
        return f"discord_http_{status}:{code}"
    return f"discord_http_{status}"


def _resync_error_detail(code: str) -> dict[str, str]:
    if code == "message_missing":
        return {
            "code": code,
            "message": (
                "The original Discord message is missing. "
                "Use Deploy to publish a new copy."
            ),
        }
    if code == "resync_message_count_mismatch":
        return {
            "code": code,
            "message": (
                "This draft now compiles into a different number of Discord messages. "
                "Use Deploy to publish a new copy."
            ),
        }
    if code == "resync_in_progress":
        return {
            "code": code,
            "message": "A Re-Sync is already in progress for this draft.",
        }
    if code == "already_synced":
        return {
            "code": code,
            "message": "This deployment is already synchronized.",
        }
    return {
        "code": "invalid_payload",
        "message": "Discord rejected the request.",
    }


async def _acquire_resync_lock(lock_key: str) -> tuple[Any | None, str | None]:
    """Best-effort Redis lock. Fail open if Redis is unavailable."""

    try:
        redis_client = await get_redis()
    except Exception:
        return None, None
    token = str(uuid.uuid4())
    try:
        acquired = bool(
            await redis_client.set(
                lock_key,
                token,
                nx=True,
                ex=RESYNC_LOCK_TTL_SECONDS,
            )
        )
    except Exception:
        await redis_client.aclose()
        return None, None
    if not acquired:
        await redis_client.aclose()
        raise HTTPException(status_code=409, detail=_resync_error_detail("resync_in_progress"))
    return redis_client, token


async def _release_resync_lock(
    redis_client: Any | None,
    lock_key: str,
    token: str | None,
) -> None:
    if redis_client is None:
        return
    try:
        current = await redis_client.get(lock_key)
        if token and current == token:
            await redis_client.delete(lock_key)
    finally:
        await redis_client.aclose()


def _http_exception_for_discord_error(error: DiscordBotAPIError) -> HTTPException:
    status = error.status_code
    if status == 403:
        return HTTPException(
            status_code=403,
            detail={
                "code": "permission_missing",
                "message": "The bot cannot post to that channel.",
            },
        )
    if status == 404:
        return HTTPException(
            status_code=404,
            detail={
                "code": "unknown_channel",
                "message": "That Discord channel was not found.",
            },
        )
    if status == 429:
        return HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Discord rate-limited this deploy. Retry shortly.",
            },
        )
    if status == 401:
        return HTTPException(
            status_code=503,
            detail={
                "code": "bot_missing",
                "message": "The Discord bot is not authorized.",
            },
        )
    if status == 400:
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_payload",
                "message": "Discord rejected the embed payload.",
            },
        )
    if status is None:
        return HTTPException(
            status_code=504,
            detail={
                "code": "timeout",
                "message": "Discord did not respond in time.",
            },
        )
    if status >= 500:
        return HTTPException(
            status_code=502,
            detail={
                "code": "bot_missing",
                "message": "Discord is temporarily unavailable.",
            },
        )
    return HTTPException(
        status_code=422,
        detail={
            "code": "invalid_payload",
            "message": "Discord rejected the request.",
        },
    )


def _log_embed_deploy(
    *,
    request_id: str,
    guild_id: str,
    message_id: str,
    embed_count: int,
    payload_count: int,
    validation_code: str | None,
    discord_status: int | str | None,
    duration_ms: int,
    idempotency_key: str | None,
    persist_ok: bool,
) -> None:
    logger.info(
        "embed_deploy request_id=%s guild_id=%s message_id=%s embed_count=%s "
        "payload_count=%s validation_code=%s discord_status=%s duration_ms=%s "
        "idempotency_key=%s persist_ok=%s",
        request_id,
        guild_id,
        message_id,
        embed_count,
        payload_count,
        validation_code or "",
        discord_status if discord_status is not None else "",
        duration_ms,
        idempotency_key or "",
        persist_ok,
    )


def _log_embed_resync(
    *,
    request_id: str,
    guild_id: str,
    message_id: str,
    delivery_id: str,
    tracked_ids: list[str],
    op: str,
    prior_version: int | None,
    target_version: int,
    code: str | None,
    discord_status: int | str | None,
    duration_ms: int,
    lock_suppressed: bool,
) -> None:
    logger.info(
        "embed_resync request_id=%s guild_id=%s message_id=%s delivery_id=%s "
        "tracked_ids=%s op=%s prior_version=%s target_version=%s code=%s "
        "discord_status=%s duration_ms=%s lock_suppressed=%s",
        request_id,
        guild_id,
        message_id,
        delivery_id,
        ",".join(tracked_ids),
        op,
        prior_version if prior_version is not None else "",
        target_version,
        code or "",
        discord_status if discord_status is not None else "",
        duration_ms,
        lock_suppressed,
    )


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/resync")
async def resync_embed_message(
    request: Request,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Reconcile the draft's latest content across its real deployments.

    Re-Sync operates over persisted ``EmbedMessageDelivery`` records (not a
    draft-owned target list). For each deployment:

    - already-current (live + deployed_version >= version): skipped (idempotent);
    - live but stale: edited in place (preserving feature-owned components);
    - missing message: recreated + repointed only when the deployment is owned
      by the Embed Library; SAR/feature-owned deployments are flagged
      ``needs_feature_repair`` for the owning feature to rebuild.

    Per-deployment results are returned so partial failures stay isolated.
    """
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    lock_key = f"embed_resync:{guild_id}:{message_id}"
    request_id = str(getattr(request.state, "request_id", "unavailable"))
    redis_client, lock_token = await _acquire_resync_lock(lock_key)
    lock_suppressed = redis_client is None
    try:
        message = await _load_message(session, guild_id, message_id)
        sar_ids = await _sar_delivery_ids(guild_id)
        deliveries = [d for d in message.deliveries if d.delivery_type == "bot"]

        payloads = _build_payloads(message)
        prior_message_ids = {
            str(delivery.id): delivery.discord_message_id
            for delivery in message.deliveries
        }
        results: list[dict[str, Any]] = []
        first_error: dict[str, Any] | None = None

        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            for delivery in deliveries:
                owner = _effective_owner(delivery, sar_ids)
                started = time.perf_counter()
                tracked_ids_before = _delivery_message_ids(delivery)
                prior_version = delivery.deployed_version
                outcome = await _resync_one_delivery(
                    bot=bot,
                    delivery=delivery,
                    message=message,
                    owner=owner,
                    payload=payloads[0],
                    payloads=payloads,
                )
                _log_embed_resync(
                    request_id=request_id,
                    guild_id=guild_id,
                    message_id=str(message_id),
                    delivery_id=str(delivery.id),
                    tracked_ids=tracked_ids_before,
                    op=str(outcome.get("status") or "unknown"),
                    prior_version=prior_version,
                    target_version=message.version or 1,
                    code=str(outcome.get("code") or "") or None,
                    discord_status=outcome.get("http_status"),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    lock_suppressed=lock_suppressed,
                )
                if first_error is None and outcome.get("status") == "error":
                    first_error = outcome
                results.append({"delivery_id": str(delivery.id), **outcome})

        await session.commit()
        message = await _load_message(session, guild_id, message_id)

        changed = _changed_deliveries(message, prior_message_ids)
        if changed:
            await reapply_menu_components_for_deliveries(
                guild_id, changed, settings.discord_bot_token
            )

        if first_error is not None:
            code = str(first_error.get("code") or "invalid_payload")
            status_code = int(first_error.get("http_status") or 422)
            raise HTTPException(status_code=status_code, detail=_resync_error_detail(code))

        return {**_serialize(message, sar_ids), "results": results}
    finally:
        await _release_resync_lock(redis_client, lock_key, lock_token)


async def _resync_one_delivery(
    *,
    bot: DiscordBotClient,
    delivery: EmbedMessageDelivery,
    message: EmbedMessage,
    owner: str,
    payload: dict[str, Any],
    payloads: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconcile a single deployment to the current draft content.

    Returns a per-delivery result dict: ``{"status": ...}`` where status is one
    of ``skipped`` (already current), ``synced`` (edited),
    ``needs_feature_repair`` (missing, feature-owned) or ``error``.
    """

    now = datetime.now(timezone.utc)
    all_payloads = payloads if payloads else [payload]
    tracked_ids = _delivery_message_ids(delivery)

    if delivery.status == "pending" and not tracked_ids:
        return {"status": "skipped"}

    # Idempotent no-op: a live, current copy needs nothing.
    if (
        tracked_ids
        and delivery.status == "synced"
        and (delivery.deployed_version or 0) >= (message.version or 1)
    ):
        return {"status": "skipped"}

    try:
        if tracked_ids and delivery.status != "message_missing":
            try:
                if len(tracked_ids) != len(all_payloads):
                    delivery.status = "error"
                    delivery.error = "resync_message_count_mismatch"
                    return {
                        "status": "error",
                        "code": "resync_message_count_mismatch",
                        "http_status": 409,
                    }
                for message_id, part in zip(tracked_ids, all_payloads, strict=True):
                    await bot.edit_channel_message(
                        delivery.channel_id,
                        message_id,
                        part,
                    )
                delivery.status = "synced"
                delivery.error = None
                delivery.deployed_version = message.version
                delivery.last_synced_at = now
                return {"status": "synced"}
            except DiscordBotAPIError as edit_error:
                if edit_error.status_code != 404:
                    raise
                # Fell through: the message vanished — treat as missing below.

        # Missing message: never recreate during Re-Sync. Feature-owned
        # deployments still return needs_feature_repair for explicit UX copy.
        delivery.status = "message_missing"
        delivery.error = "Message missing in Discord."
        if owner != OWNER_LIBRARY:
            return {"status": "needs_feature_repair"}
        return {"status": "error", "code": "message_missing", "http_status": 404}
    except DiscordBotAPIError as error:
        delivery.status = _status_for_error(error)
        delivery.error = _safe_discord_error(error)
        http_error = _http_exception_for_discord_error(error)
        detail = http_error.detail if isinstance(http_error.detail, dict) else {}
        code = detail.get("code") if isinstance(detail.get("code"), str) else "invalid_payload"
        return {
            "status": "error",
            "error": _safe_discord_error(error),
            "code": code,
            "http_status": http_error.status_code,
        }


@router.post(
    "/guilds/{guild_id}/embed-messages/{message_id}/deliveries/{delivery_id}/resync"
)
async def resync_embed_delivery(
    request: Request,
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    delivery_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Re-sync a single published instance (delivery) in place.

    Edits the exact tracked Discord message. If it 404s (deleted externally),
    a fresh message is sent only when the deployment is owned by the Embed
    Library; feature-owned (e.g. SAR) deployments are left flagged for repair by
    their owning feature since they require components.
    """

    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    lock_key = f"embed_resync:{guild_id}:{message_id}:{delivery_id}"
    request_id = str(getattr(request.state, "request_id", "unavailable"))
    redis_client, lock_token = await _acquire_resync_lock(lock_key)
    lock_suppressed = redis_client is None
    try:
        message = await _load_message(session, guild_id, message_id)
        delivery = next(
            (d for d in message.deliveries if d.id == delivery_id),
            None,
        )
        if delivery is None:
            raise HTTPException(status_code=404, detail="Delivery not found.")

        sar_ids = await _sar_delivery_ids(guild_id)
        owner = _effective_owner(delivery, sar_ids)
        prior_message_ids = {str(delivery.id): delivery.discord_message_id}
        payloads = _build_payloads(message)

        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            started = time.perf_counter()
            tracked_ids_before = _delivery_message_ids(delivery)
            prior_version = delivery.deployed_version
            outcome = await _resync_one_delivery(
                bot=bot,
                delivery=delivery,
                message=message,
                owner=owner,
                payload=payloads[0],
                payloads=payloads,
            )
        _log_embed_resync(
            request_id=request_id,
            guild_id=guild_id,
            message_id=str(message_id),
            delivery_id=str(delivery.id),
            tracked_ids=tracked_ids_before,
            op=str(outcome.get("status") or "unknown"),
            prior_version=prior_version,
            target_version=message.version or 1,
            code=str(outcome.get("code") or "") or None,
            discord_status=outcome.get("http_status"),
            duration_ms=int((time.perf_counter() - started) * 1000),
            lock_suppressed=lock_suppressed,
        )

        await session.commit()
        if outcome.get("status") == "error":
            code = str(outcome.get("code") or "invalid_payload")
            status_code = int(outcome.get("http_status") or 422)
            raise HTTPException(
                status_code=status_code,
                detail=_resync_error_detail(code),
            )

        message = await _load_message(session, guild_id, message_id)

        changed = _changed_deliveries(message, prior_message_ids)
        if changed:
            await reapply_menu_components_for_deliveries(
                guild_id, changed, settings.discord_bot_token
            )

        return _serialize(message, sar_ids)
    finally:
        await _release_resync_lock(redis_client, lock_key, lock_token)


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
    return {
        **_serialize(message, await _sar_delivery_ids(guild_id)),
        "probed": probed,
    }


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
