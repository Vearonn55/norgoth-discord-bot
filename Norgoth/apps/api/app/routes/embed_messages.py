"""Guild-scoped reusable Discord embed messages: CRUD, send, and edit-sync."""

from __future__ import annotations

import logging
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


class EmbedMessageBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=MAX_STORED_MARKDOWN_CHARS)
    embed_json: Optional[dict[str, Any]] = None
    # Deprecated: drafts are content-only. Accepted for one release for backward
    # compatibility with older clients, but ignored (never persisted). Removed
    # from the schema once the column is dropped (migration 0013).


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

    synced | out_of_date | missing | needs_feature_repair | error
    """

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
    guild_id: str = Path(pattern=SNOWFLAKE),
    message_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    message = await _load_message(session, guild_id, message_id)
    payloads = _build_payloads(message)

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        sent: dict[str, Any] | None = None
        try:
            for payload in payloads:
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
                detail=_discord_send_error_code(error),
            ) from error

    delivery = EmbedMessageDelivery(
        embed_message_id=message.id,
        guild_id=guild_id,
        channel_id=body.channel_id,
        discord_message_id=str(sent.get("id") or "") or None,
        delivery_type="bot",
        owner_feature=OWNER_LIBRARY,
        status="synced",
        deployed_version=message.version,
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(delivery)
    await session.commit()

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


def _discord_send_error_code(error: DiscordBotAPIError) -> str:
    status = error.status_code
    if status == 403:
        return "permission_missing"
    if status == 404:
        return "unknown_channel"
    if status == 400:
        return "invalid_payload"
    if status == 429:
        return "rate_limited"
    if status is None:
        return "timeout"
    return "bot_missing"


@router.post("/guilds/{guild_id}/embed-messages/{message_id}/resync")
async def resync_embed_message(
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

    message = await _load_message(session, guild_id, message_id)
    sar_ids = await _sar_delivery_ids(guild_id)
    deliveries = [d for d in message.deliveries if d.delivery_type == "bot"]

    payload = _build_payload(message)
    prior_message_ids = {
        str(delivery.id): delivery.discord_message_id
        for delivery in message.deliveries
    }
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        for delivery in deliveries:
            owner = _effective_owner(delivery, sar_ids)
            outcome = await _resync_one_delivery(
                bot=bot,
                delivery=delivery,
                message=message,
                owner=owner,
                payload=payload,
            )
            results.append({"delivery_id": str(delivery.id), **outcome})

    await session.commit()
    message = await _load_message(session, guild_id, message_id)

    changed = _changed_deliveries(message, prior_message_ids)
    if changed:
        await reapply_menu_components_for_deliveries(
            guild_id, changed, settings.discord_bot_token
        )

    return {**_serialize(message, sar_ids), "results": results}


async def _resync_one_delivery(
    *,
    bot: DiscordBotClient,
    delivery: EmbedMessageDelivery,
    message: EmbedMessage,
    owner: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile a single deployment to the current draft content.

    Returns a per-delivery result dict: ``{"status": ...}`` where status is one
    of ``skipped`` (already current), ``synced`` (edited/recreated),
    ``needs_feature_repair`` (missing, feature-owned) or ``error``.
    """

    now = datetime.now(timezone.utc)

    # Idempotent no-op: a live, current copy needs nothing.
    if (
        delivery.discord_message_id
        and delivery.status == "synced"
        and (delivery.deployed_version or 0) >= (message.version or 1)
    ):
        return {"status": "skipped"}

    try:
        if delivery.discord_message_id and delivery.status != "message_missing":
            try:
                await bot.edit_channel_message(
                    delivery.channel_id,
                    str(delivery.discord_message_id),
                    payload,
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

        # Missing message: only the Embed Library may recreate a plain embed.
        # Feature-owned deployments (e.g. SAR) need their components, so defer.
        if owner != OWNER_LIBRARY:
            delivery.status = "message_missing"
            delivery.error = (
                "Message missing; owning feature must repair (has components)."
            )
            return {"status": "needs_feature_repair"}

        sent = await bot.send_channel_message(delivery.channel_id, payload)
        delivery.discord_message_id = str(sent.get("id") or "") or None
        delivery.status = "synced"
        delivery.error = None
        delivery.deployed_version = message.version
        delivery.last_synced_at = now
        return {"status": "synced"}
    except DiscordBotAPIError as error:
        delivery.status = _status_for_error(error)
        delivery.error = str(error)
        return {"status": "error", "error": str(error)}


@router.post(
    "/guilds/{guild_id}/embed-messages/{message_id}/deliveries/{delivery_id}/resync"
)
async def resync_embed_delivery(
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
    payload = _build_payload(message)

    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        outcome = await _resync_one_delivery(
            bot=bot,
            delivery=delivery,
            message=message,
            owner=owner,
            payload=payload,
        )

    if outcome.get("status") == "error":
        await session.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Discord rejected the re-sync: {outcome.get('error')}",
        )

    await session.commit()
    message = await _load_message(session, guild_id, message_id)

    changed = _changed_deliveries(message, prior_message_ids)
    if changed:
        await reapply_menu_components_for_deliveries(
            guild_id, changed, settings.discord_bot_token
        )

    return _serialize(message, sar_ids)


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
