"""Guild-scoped content notification admin API."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, NoReturn, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.dependencies_auth import (
    guild_manager_dependency,
    require_operator_session,
)
from app.db.session import get_database_session
from app.core.config import get_settings
from app.integrations.content_platforms.registry import get_adapter, platform_availability
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformAdapterError,
    PlatformBlockedError,
    PlatformType,
    ResolvedCreator,
)
from app.integrations.discord.bot_rest import DiscordBotClient
from app.models.content_notifications import (
    ContentCreatorSource,
    GuildContentSubscription,
    NormalizedContentEventRow,
    NotificationDeliveryAttempt,
    NotificationJob,
    NotificationSenderStyle,
    NotificationTemplate,
    PlatformMonitorCursor,
    PlatformSubscription,
)
from app.services.content_notifications.avatar import (
    persistable_source_avatar,
    persistable_webhook_avatar,
    parse_account_platform_filter,
    read_resolve_cache,
    refresh_stale_avatars,
    write_resolve_cache,
)
from app.services.content_notifications.i18n import normalize_locale
from app.services.content_notifications.fanout import (
    ensure_source,
    event_from_row,
    persist_and_fanout,
)
from app.services.content_notifications.payload_builder import build_discord_payload
from app.services.content_notifications.permission_checks import explain_permission_gap
from app.services.content_notifications.queue import enqueue_job, worker_online
from app.services.content_notifications.quotas import (
    ACTIVE_LIMITS,
    ContentNotificationQuotaError,
    assert_can_create,
    assert_can_enable,
    guild_platform_usage,
    total_limit_for,
)
from app.services.content_notifications.rate_limit import throttle
from app.services.content_notifications.tag_registry import (
    DEFAULT_TEMPLATES,
    TAG_REGISTRY,
    default_embed_json,
)
from app.services.content_notifications.tag_resolver import preview_placeholders
from app.services.content_notifications.webhook_manager import (
    WebhookManagerError,
    ensure_managed_webhook,
    execute_managed_webhook,
)

logger = logging.getLogger("norgoth.content.api")

# Guild-scoped admin routes require guild-manager auth.
router = APIRouter(
    tags=["Content Notifications"],
    dependencies=[Depends(guild_manager_dependency())],
)

# Non-guild static catalog routes (platform/tag metadata) require only a valid
# operator session, not guild-manager auth, since they carry no guild id.
catalog_router = APIRouter(
    tags=["Content Notifications"],
    dependencies=[Depends(require_operator_session)],
)

SNOWFLAKE = r"^[0-9]{5,25}$"
PlatformLiteral = Literal["youtube", "twitch", "kick", "x", "tiktok"]


class ResolveAccountRequest(BaseModel):
    platform: PlatformLiteral
    url: str = Field(min_length=1, max_length=500)


class CreateSubscriptionRequest(BaseModel):
    platform: PlatformLiteral
    url: str = Field(min_length=1, max_length=500)
    destination_channel_id: str = Field(pattern=SNOWFLAKE)
    ping_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    template_id: Optional[UUID] = None
    sender_style_id: Optional[UUID] = None
    event_types: list[str] = Field(default_factory=list)
    enabled: bool = True
    notification_locale: Optional[str] = Field(default="en", max_length=5)


class UpdateSubscriptionRequest(BaseModel):
    destination_channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    ping_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    template_id: Optional[UUID] = None
    sender_style_id: Optional[UUID] = None
    event_types: Optional[list[str]] = None
    enabled: Optional[bool] = None
    notification_locale: Optional[str] = Field(default=None, max_length=5)


class TemplateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    platform_default_for: Optional[PlatformLiteral] = None
    content: str = Field(default="", max_length=2000)
    embed_json: Optional[dict[str, Any]] = None


class SenderStyleBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class SenderStyleUpdateBody(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class TestNotificationRequest(BaseModel):
    subscription_id: UUID


class ForceNotificationRequest(BaseModel):
    subscription_id: UUID
    content_url: str = Field(min_length=1, max_length=500)


class PreviewRequest(BaseModel):
    platform: PlatformLiteral = "youtube"
    content: str = ""
    embed_json: Optional[dict[str, Any]] = None
    ping_role_id: Optional[str] = None


def _serialize_resolved_creator(
    creator: ResolvedCreator,
    *,
    available: bool,
    reason: str | None,
) -> dict[str, Any]:
    platform = creator.platform.value
    return {
        "platform": platform,
        "platform_creator_id": creator.platform_creator_id,
        "username": creator.username,
        "display_name": creator.display_name,
        "profile_url": creator.profile_url,
        "avatar_url": persistable_source_avatar(platform, creator.avatar_url),
        "canonical_url": creator.canonical_url,
        "available": available,
        "reason": reason,
    }


def _adapter_http_status(code: str) -> int:
    if code in {"rate_limited", "quota_exhausted"}:
        return 429
    return 400


def _raise_adapter_http(error: PlatformAdapterError) -> NoReturn:
    raise HTTPException(
        status_code=_adapter_http_status(error.code),
        detail={"code": error.code, "message": str(error)},
    ) from error


async def _resolve_creator(
    *,
    guild_id: str,
    platform: str,
    url: str,
) -> ResolvedCreator:
    cached = await read_resolve_cache(guild_id, platform, url)
    if cached is not None:
        return cached
    adapter = get_adapter(platform)
    await throttle(platform)
    creator = await adapter.resolve_account(url)
    await write_resolve_cache(guild_id, platform, url, creator)
    return creator


def _serialize_source(source: ContentCreatorSource) -> dict[str, Any]:
    return {
        "id": str(source.id),
        "platform": source.platform,
        "platform_creator_id": source.platform_creator_id,
        "username": source.username,
        "display_name": source.display_name,
        "profile_url": source.profile_url,
        "avatar_url": source.avatar_url,
        "canonical_url": source.canonical_url,
        "monitor_status": source.monitor_status,
        "last_event_at": source.last_event_at.isoformat() if source.last_event_at else None,
    }


def _serialize_subscription(sub: GuildContentSubscription) -> dict[str, Any]:
    return {
        "id": str(sub.id),
        "guild_id": sub.guild_id,
        "source": _serialize_source(sub.source) if sub.source else None,
        "destination_channel_id": sub.destination_channel_id,
        "ping_role_id": sub.ping_role_id,
        "template_id": str(sub.template_id) if sub.template_id else None,
        "sender_style_id": str(sub.sender_style_id) if sub.sender_style_id else None,
        "event_types": sub.event_types or [],
        "enabled": sub.enabled,
        "status": sub.status,
        "notification_locale": sub.notification_locale,
        "last_event_at": sub.last_event_at.isoformat() if sub.last_event_at else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


async def _assert_guild_owned_template(
    session: AsyncSession,
    *,
    guild_id: str,
    template_id: UUID | None,
) -> None:
    if template_id is None:
        return
    owned = await session.scalar(
        select(NotificationTemplate.id).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.guild_id == guild_id,
        )
    )
    if owned is None:
        raise HTTPException(
            status_code=400,
            detail="template_id does not belong to this guild.",
        )


async def _assert_guild_owned_sender_style(
    session: AsyncSession,
    *,
    guild_id: str,
    sender_style_id: UUID | None,
) -> None:
    if sender_style_id is None:
        return
    owned = await session.scalar(
        select(NotificationSenderStyle.id).where(
            NotificationSenderStyle.id == sender_style_id,
            NotificationSenderStyle.guild_id == guild_id,
        )
    )
    if owned is None:
        raise HTTPException(
            status_code=400,
            detail="sender_style_id does not belong to this guild.",
        )


@catalog_router.get("/content-notifications/platforms")
async def list_platforms() -> dict[str, Any]:
    platforms = platform_availability()
    for row in platforms:
        platform = str(row["platform"])
        row["active_limit"] = ACTIVE_LIMITS.get(platform, 0)
        row["total_limit"] = total_limit_for(platform)
    return {"platforms": platforms}


@catalog_router.get("/content-notifications/tags")
async def list_tags() -> dict[str, Any]:
    return {
        "tags": [
            {
                "name": tag.name,
                "description": tag.description,
                "supported_event_types": [e.value for e in tag.supported_event_types],
            }
            for tag in TAG_REGISTRY.values()
        ]
    }


@router.post("/guilds/{guild_id}/content-notifications/resolve")
async def resolve_account(
    guild_id: str,
    body: ResolveAccountRequest,
) -> dict[str, Any]:
    adapter = get_adapter(body.platform)
    try:
        creator = await _resolve_creator(
            guild_id=guild_id,
            platform=body.platform,
            url=body.url,
        )
    except PlatformBlockedError as error:
        _raise_adapter_http(error)
    except PlatformAdapterError as error:
        _raise_adapter_http(error)
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_timeout",
                "message": "Creator lookup timed out.",
            },
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_error",
                "message": "Creator lookup failed.",
            },
        ) from error
    return _serialize_resolved_creator(
        creator,
        available=adapter.is_available(),
        reason=adapter.availability_reason(),
    )


@router.get("/guilds/{guild_id}/content-notifications/accounts")
async def list_accounts(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
    platform: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        platform_filter = parse_account_platform_filter(platform)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_platform",
                "message": "Platform filter must be youtube, twitch, kick, x, or all.",
            },
        ) from None

    filters = [GuildContentSubscription.guild_id == guild_id]
    count_stmt = select(func.count()).select_from(GuildContentSubscription)
    list_stmt = select(GuildContentSubscription)
    if platform_filter:
        count_stmt = count_stmt.join(
            ContentCreatorSource,
            ContentCreatorSource.id == GuildContentSubscription.source_id,
        ).where(
            *filters,
            ContentCreatorSource.platform == platform_filter,
        )
        list_stmt = list_stmt.join(
            ContentCreatorSource,
            ContentCreatorSource.id == GuildContentSubscription.source_id,
        ).where(
            *filters,
            ContentCreatorSource.platform == platform_filter,
        )
    else:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = int((await session.scalar(count_stmt)) or 0)
    rows = (
        await session.scalars(
            list_stmt.options(selectinload(GuildContentSubscription.source))
            .order_by(GuildContentSubscription.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    await refresh_stale_avatars(
        session, [row.source for row in rows if row.source is not None]
    )
    await session.commit()
    usage = await guild_platform_usage(session, guild_id=guild_id)
    usage_by_platform = {item["platform"]: item for item in usage}
    platforms = platform_availability()
    for row in platforms:
        platform = str(row["platform"])
        stats = usage_by_platform.get(platform) or {
            "active_limit": ACTIVE_LIMITS.get(platform, 0),
            "active_count": 0,
            "active_remaining": ACTIVE_LIMITS.get(platform, 0),
            "total_limit": total_limit_for(platform),
            "total_count": 0,
            "total_remaining": total_limit_for(platform),
        }
        row.update(stats)
    return {
        "accounts": [_serialize_subscription(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "worker_online": await worker_online(),
        "platforms": platforms,
        "platform_usage": usage,
    }


@router.post("/guilds/{guild_id}/content-notifications/accounts")
async def create_account(
    guild_id: str,
    body: CreateSubscriptionRequest,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    adapter = get_adapter(body.platform)
    try:
        creator = await _resolve_creator(
            guild_id=guild_id,
            platform=body.platform,
            url=body.url,
        )
    except PlatformBlockedError as error:
        _raise_adapter_http(error)
    except PlatformAdapterError as error:
        _raise_adapter_http(error)
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_timeout",
                "message": "Creator lookup timed out.",
            },
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_error",
                "message": "Creator lookup failed.",
            },
        ) from error

    source = await ensure_source(
        session,
        platform=creator.platform.value,
        platform_creator_id=creator.platform_creator_id,
        username=creator.username,
        display_name=creator.display_name,
        profile_url=creator.profile_url,
        avatar_url=creator.avatar_url,
        canonical_url=creator.canonical_url,
        metadata=creator.metadata,
        monitor_status="blocked" if not adapter.is_available() else "active",
    )

    try:
        await assert_can_create(
            session,
            guild_id=guild_id,
            platform=creator.platform.value,
            will_be_enabled=body.enabled,
        )
    except ContentNotificationQuotaError as error:
        raise HTTPException(status_code=400, detail=error.as_detail()) from error

    existing = await session.scalar(
        select(GuildContentSubscription).where(
            GuildContentSubscription.guild_id == guild_id,
            GuildContentSubscription.source_id == source.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Creator already monitored in this guild.")

    event_types = body.event_types or _default_event_types(creator.platform)
    template_id = body.template_id
    if template_id is None:
        template_id = await _ensure_default_template(session, guild_id, creator.platform)
    await _assert_guild_owned_template(
        session, guild_id=guild_id, template_id=template_id
    )
    await _assert_guild_owned_sender_style(
        session, guild_id=guild_id, sender_style_id=body.sender_style_id
    )

    # Ensure managed webhook exists when bot token + encryption are configured.
    settings = get_settings()
    if settings.discord_bot_token and getattr(settings, "webhook_encryption_key", None):
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            try:
                await ensure_managed_webhook(
                    session,
                    bot,
                    guild_id=guild_id,
                    channel_id=body.destination_channel_id,
                )
            except WebhookManagerError as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Discord webhook setup failed: {error}",
                ) from error

    sub = GuildContentSubscription(
        guild_id=guild_id,
        source_id=source.id,
        destination_channel_id=body.destination_channel_id,
        ping_role_id=body.ping_role_id,
        template_id=template_id,
        sender_style_id=body.sender_style_id,
        event_types=event_types,
        enabled=body.enabled,
        status="waiting_first_event" if adapter.is_available() else "blocked",
        notification_locale=normalize_locale(body.notification_locale),
    )
    session.add(sub)
    await session.flush()

    # Upstream subscribe / poll cursor
    if adapter.supports_push() and adapter.is_available():
        result = await adapter.subscribe(creator)
        if result:
            secret = result.get("secret")
            encrypted = None
            if secret and getattr(settings, "webhook_encryption_key", None):
                from app.security.secret_box import require_secret_box

                encrypted = require_secret_box().encrypt(str(secret))
            existing_sub = await session.scalar(
                select(PlatformSubscription).where(
                    PlatformSubscription.source_id == source.id,
                    PlatformSubscription.transport == _transport_for(creator.platform),
                )
            )
            if existing_sub:
                existing_sub.external_subscription_id = result.get(
                    "external_subscription_id"
                )
                existing_sub.lease_expires_at = datetime.now(timezone.utc) + timedelta(
                    days=5
                )
                if encrypted is not None:
                    existing_sub.callback_secret_encrypted = encrypted
                existing_sub.status = "active"
            else:
                session.add(
                    PlatformSubscription(
                        source_id=source.id,
                        transport=_transport_for(creator.platform),
                        external_subscription_id=result.get("external_subscription_id"),
                        lease_expires_at=datetime.now(timezone.utc) + timedelta(days=5),
                        callback_secret_encrypted=encrypted,
                        status="active",
                    )
                )
        else:
            # Account is saved, but live events will not arrive until subscribe works.
            sub.status = "upstream_subscribe_failed"
            logger.warning(
                "Push subscribe failed for %s/%s guild=%s",
                creator.platform.value,
                creator.platform_creator_id,
                guild_id,
            )
    else:
        existing_cursor = await session.scalar(
            select(PlatformMonitorCursor).where(
                PlatformMonitorCursor.source_id == source.id
            )
        )
        if existing_cursor is None:
            session.add(
                PlatformMonitorCursor(
                    source_id=source.id,
                    next_check_at=datetime.now(timezone.utc),
                )
            )

    await session.commit()
    await session.refresh(sub, attribute_names=["source"])
    return _serialize_subscription(sub)


@router.patch("/guilds/{guild_id}/content-notifications/accounts/{subscription_id}")
async def update_account(
    guild_id: str,
    subscription_id: UUID,
    body: UpdateSubscriptionRequest,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    sub = await session.scalar(
        select(GuildContentSubscription)
        .where(
            GuildContentSubscription.id == subscription_id,
            GuildContentSubscription.guild_id == guild_id,
        )
        .options(selectinload(GuildContentSubscription.source))
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    fields_set = body.model_fields_set
    if body.destination_channel_id is not None:
        sub.destination_channel_id = body.destination_channel_id
    if "ping_role_id" in fields_set:
        sub.ping_role_id = body.ping_role_id or None
    if "template_id" in fields_set:
        await _assert_guild_owned_template(
            session, guild_id=guild_id, template_id=body.template_id
        )
        sub.template_id = body.template_id
    if "sender_style_id" in fields_set:
        await _assert_guild_owned_sender_style(
            session, guild_id=guild_id, sender_style_id=body.sender_style_id
        )
        sub.sender_style_id = body.sender_style_id
    if body.event_types is not None:
        sub.event_types = body.event_types
    if body.enabled is not None:
        if body.enabled and not sub.enabled:
            try:
                await assert_can_enable(
                    session,
                    guild_id=guild_id,
                    platform=sub.source.platform,
                    currently_enabled=sub.enabled,
                )
            except ContentNotificationQuotaError as error:
                raise HTTPException(status_code=400, detail=error.as_detail()) from error
        sub.enabled = body.enabled
        if not body.enabled:
            sub.status = "paused"
    if "notification_locale" in fields_set and body.notification_locale is not None:
        sub.notification_locale = normalize_locale(body.notification_locale)
    await session.commit()
    await session.refresh(sub, attribute_names=["source"])
    return _serialize_subscription(sub)


@router.delete("/guilds/{guild_id}/content-notifications/accounts/{subscription_id}")
async def delete_account(
    guild_id: str,
    subscription_id: UUID,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    sub = await session.scalar(
        select(GuildContentSubscription)
        .where(
            GuildContentSubscription.id == subscription_id,
            GuildContentSubscription.guild_id == guild_id,
        )
        .options(selectinload(GuildContentSubscription.source))
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    source = sub.source
    source_id = sub.source_id
    await session.delete(sub)
    await session.flush()

    # Drop Kick/Twitch upstream subscriptions when no guild still monitors the source.
    remaining = await session.scalar(
        select(func.count())
        .select_from(GuildContentSubscription)
        .where(GuildContentSubscription.source_id == source_id)
    )
    if int(remaining or 0) == 0 and source is not None:
        adapter = get_adapter(source.platform)
        if adapter.supports_push() and adapter.is_available():
            creator = ResolvedCreator(
                platform=PlatformType(source.platform),
                platform_creator_id=source.platform_creator_id,
                username=source.username,
                display_name=source.display_name,
                profile_url=source.profile_url,
                avatar_url=source.avatar_url,
                canonical_url=source.canonical_url,
            )
            try:
                await adapter.unsubscribe(creator)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Upstream unsubscribe failed for %s/%s",
                    source.platform,
                    source.platform_creator_id,
                )
        platform_subs = (
            await session.scalars(
                select(PlatformSubscription).where(
                    PlatformSubscription.source_id == source_id
                )
            )
        ).all()
        for row in platform_subs:
            await session.delete(row)

    await session.commit()
    return {"ok": True}


@router.get("/guilds/{guild_id}/content-notifications/templates")
async def list_templates(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(NotificationTemplate)
            .where(NotificationTemplate.guild_id == guild_id)
            .order_by(NotificationTemplate.created_at.desc())
        )
    ).all()
    return {
        "templates": [
            {
                "id": str(row.id),
                "name": row.name,
                "platform_default_for": row.platform_default_for,
                "content": row.content,
                "embed_json": row.embed_json,
            }
            for row in rows
        ]
    }


@router.post("/guilds/{guild_id}/content-notifications/templates")
async def create_template(
    guild_id: str,
    body: TemplateBody,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = NotificationTemplate(
        guild_id=guild_id,
        name=body.name,
        platform_default_for=body.platform_default_for,
        content=body.content,
        embed_json=body.embed_json,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "id": str(row.id),
        "name": row.name,
        "platform_default_for": row.platform_default_for,
        "content": row.content,
        "embed_json": row.embed_json,
    }


@router.put("/guilds/{guild_id}/content-notifications/templates/{template_id}")
async def update_template(
    guild_id: str,
    template_id: UUID,
    body: TemplateBody,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if row.guild_id != guild_id:
        raise HTTPException(
            status_code=400,
            detail="template_id does not belong to this guild.",
        )
    row.name = body.name
    row.platform_default_for = body.platform_default_for
    row.content = body.content
    row.embed_json = body.embed_json
    await session.commit()
    return {
        "id": str(row.id),
        "name": row.name,
        "platform_default_for": row.platform_default_for,
        "content": row.content,
        "embed_json": row.embed_json,
    }


@router.delete("/guilds/{guild_id}/content-notifications/templates/{template_id}")
async def delete_template(
    guild_id: str,
    template_id: UUID,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.guild_id == guild_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await session.delete(row)
    await session.commit()
    return {"ok": True}


def _serialize_sender_style(row: NotificationSenderStyle) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "display_name": row.display_name,
        "avatar_url": row.avatar_url,
    }


def _validated_style_avatar(url: str | None) -> str | None:
    if url is None or not str(url).strip():
        return None
    normalized = persistable_webhook_avatar(url)
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_avatar_url",
                "message": (
                    "Avatar URL must be a public https image Discord can fetch."
                ),
            },
        )
    return normalized


@router.get("/guilds/{guild_id}/content-notifications/sender-styles")
async def list_sender_styles(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(NotificationSenderStyle).where(
                NotificationSenderStyle.guild_id == guild_id
            )
        )
    ).all()
    return {"styles": [_serialize_sender_style(row) for row in rows]}


@router.post("/guilds/{guild_id}/content-notifications/sender-styles")
async def create_sender_style(
    guild_id: str,
    body: SenderStyleBody,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = NotificationSenderStyle(
        guild_id=guild_id,
        display_name=body.display_name,
        avatar_url=_validated_style_avatar(body.avatar_url),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _serialize_sender_style(row)


@router.patch("/guilds/{guild_id}/content-notifications/sender-styles/{style_id}")
async def update_sender_style(
    guild_id: str,
    style_id: UUID,
    body: SenderStyleUpdateBody,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(NotificationSenderStyle).where(
            NotificationSenderStyle.id == style_id,
            NotificationSenderStyle.guild_id == guild_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Sender style not found")
    next_name = row.display_name
    next_avatar = row.avatar_url
    if "display_name" in body.model_fields_set and body.display_name is not None:
        next_name = body.display_name
    if "avatar_url" in body.model_fields_set:
        next_avatar = _validated_style_avatar(body.avatar_url)
    row.display_name = next_name
    row.avatar_url = next_avatar
    await session.commit()
    await session.refresh(row)
    return _serialize_sender_style(row)


@router.delete("/guilds/{guild_id}/content-notifications/sender-styles/{style_id}")
async def delete_sender_style(
    guild_id: str,
    style_id: UUID,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(NotificationSenderStyle).where(
            NotificationSenderStyle.id == style_id,
            NotificationSenderStyle.guild_id == guild_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Sender style not found")
    await session.delete(row)
    await session.commit()
    return {"ok": True}


@router.post("/guilds/{guild_id}/content-notifications/preview")
async def preview_notification(guild_id: str, body: PreviewRequest) -> dict[str, Any]:
    _ = guild_id
    event = preview_placeholders(body.platform)
    payload = build_discord_payload(
        content_template=body.content or DEFAULT_TEMPLATES[PlatformType(body.platform)],
        embed_template=body.embed_json,
        event=event,
        ping_role_id=body.ping_role_id,
    )
    return {"payload": payload}


@router.post("/guilds/{guild_id}/content-notifications/test")
async def test_notification(
    guild_id: str,
    body: TestNotificationRequest,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    sub = await session.scalar(
        select(GuildContentSubscription)
        .where(
            GuildContentSubscription.id == body.subscription_id,
            GuildContentSubscription.guild_id == guild_id,
        )
        .options(
            selectinload(GuildContentSubscription.source),
            selectinload(GuildContentSubscription.template),
            selectinload(GuildContentSubscription.sender_style),
        )
    )
    if sub is None or sub.source is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not await worker_online():
        raise HTTPException(
            status_code=503,
            detail="Content notification worker is offline. Start content-worker and retry.",
        )

    adapter = get_adapter(sub.source.platform)
    creator = ResolvedCreator(
        platform=PlatformType(sub.source.platform),
        platform_creator_id=sub.source.platform_creator_id,
        username=sub.source.username,
        display_name=sub.source.display_name,
        profile_url=sub.source.profile_url,
        avatar_url=sub.source.avatar_url,
        canonical_url=sub.source.canonical_url,
    )
    # Kick/Twitch may be offline or API may fail — still deliver a synthetic test.
    latest_event = None
    try:
        latest = await adapter.fetch_latest(creator, limit=1)
        latest_event = latest[0] if latest else None
    except Exception:  # noqa: BLE001
        logger.exception(
            "fetch_latest failed during test for %s/%s",
            sub.source.platform,
            sub.source.platform_creator_id,
        )

    event = _manual_test_event(
        creator=creator,
        subscription_id=sub.id,
        latest=latest_event,
        event_types=sub.event_types or [],
    )

    fanout = await persist_and_fanout(session, event, source=sub.source)
    row = fanout.event
    if row is None:
        raise HTTPException(status_code=500, detail="Could not persist test event.")

    # Ensure THIS subscription gets a job even if disabled / type-filtered.
    job_id = await _ensure_job_row(
        session,
        event_id=row.id,
        subscription_id=sub.id,
    )
    await session.commit()
    await enqueue_job(str(job_id))
    return {"ok": True, "job_id": str(job_id), "event_id": str(row.id)}


@router.post("/guilds/{guild_id}/content-notifications/force")
async def force_notification(
    guild_id: str,
    body: ForceNotificationRequest,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    sub = await session.scalar(
        select(GuildContentSubscription)
        .where(
            GuildContentSubscription.id == body.subscription_id,
            GuildContentSubscription.guild_id == guild_id,
        )
        .options(selectinload(GuildContentSubscription.source))
    )
    if sub is None or sub.source is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not await worker_online():
        raise HTTPException(
            status_code=503,
            detail="Content notification worker is offline. Start content-worker and retry.",
        )

    adapter = get_adapter(sub.source.platform)
    creator = ResolvedCreator(
        platform=PlatformType(sub.source.platform),
        platform_creator_id=sub.source.platform_creator_id,
        username=sub.source.username,
        display_name=sub.source.display_name,
        profile_url=sub.source.profile_url,
        avatar_url=sub.source.avatar_url,
        canonical_url=sub.source.canonical_url,
    )
    latest = await adapter.fetch_latest(creator, limit=10)
    match = next(
        (e for e in latest if e.content_url and body.content_url in e.content_url),
        None,
    )
    if match is None and latest:
        # Allow exact external id pasted as URL tail.
        match = next(
            (e for e in latest if e.external_content_id in body.content_url),
            None,
        )
    if match is None:
        raise HTTPException(
            status_code=400,
            detail="Content URL does not match recent posts for this creator.",
        )

    # Unique id so force can re-deliver the same live session.
    forced = NormalizedContentEvent(
        platform=match.platform,
        event_type=match.event_type,
        external_content_id=f"force:{sub.id}:{uuid4()}:{match.external_content_id}",
        creator_platform_id=match.creator_platform_id,
        creator_name=match.creator_name,
        creator_avatar=match.creator_avatar,
        title=match.title,
        description=match.description,
        content_url=match.content_url,
        playable_url=match.playable_url,
        thumbnail_url=match.thumbnail_url,
        published_at=match.published_at or datetime.now(timezone.utc),
        is_live=match.is_live,
        game=match.game,
        category=match.category,
        viewer_count=match.viewer_count,
        raw_metadata={**(match.raw_metadata or {}), "forced": True},
    )

    fanout = await persist_and_fanout(session, forced, source=sub.source)
    row = fanout.event
    if row is None:
        raise HTTPException(status_code=500, detail="Could not persist forced event.")

    job_id = await _ensure_job_row(
        session,
        event_id=row.id,
        subscription_id=sub.id,
    )
    await session.commit()
    await enqueue_job(str(job_id))
    return {"ok": True, "job_id": str(job_id), "event_id": str(row.id)}


async def _ensure_job_row(
    session: AsyncSession,
    *,
    event_id: UUID,
    subscription_id: UUID,
) -> UUID:
    """Insert-or-reuse the notification job row (caller enqueues after commit)."""

    stmt = (
        pg_insert(NotificationJob)
        .values(
            event_id=event_id,
            subscription_id=subscription_id,
            status="queued",
            attempt_count=0,
            next_attempt_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(
            constraint="uq_notification_jobs_event_subscription",
        )
        .returning(NotificationJob.id)
    )
    job_id = (await session.execute(stmt)).scalar_one_or_none()
    if job_id is not None:
        return job_id

    existing = await session.scalar(
        select(NotificationJob).where(
            NotificationJob.event_id == event_id,
            NotificationJob.subscription_id == subscription_id,
        )
    )
    if existing is None:
        raise HTTPException(
            status_code=500,
            detail="Could not create notification job for test delivery.",
        )
    if existing.status in {"succeeded", "dead", "failed"}:
        existing.status = "queued"
        existing.last_error = None
        existing.next_attempt_at = datetime.now(timezone.utc)
    return existing.id


def _manual_test_event(
    *,
    creator: ResolvedCreator,
    subscription_id: UUID,
    latest: NormalizedContentEvent | None,
    event_types: list[str],
) -> NormalizedContentEvent:
    """Build a unique event for the dashboard Test button.

    Always uses a fresh external id so retests are not swallowed by dedupe.
    If the creator is offline / has no recent content, synthesize a sample
    event so Discord delivery can still be verified.
    """

    preferred = None
    if event_types:
        for value in event_types:
            try:
                preferred = ContentEventType(value)
                break
            except ValueError:
                continue
    if preferred is None:
        preferred = (
            latest.event_type
            if latest is not None
            else ContentEventType.STREAM_STARTED
        )

    if latest is not None:
        base = latest
        title = base.title or f"[Test] {creator.display_name}"
        return NormalizedContentEvent(
            platform=base.platform,
            event_type=preferred if preferred == base.event_type else base.event_type,
            external_content_id=f"manual-test:{subscription_id}:{uuid4()}",
            creator_platform_id=base.creator_platform_id,
            creator_name=base.creator_name or creator.display_name,
            creator_avatar=base.creator_avatar or creator.avatar_url,
            title=title,
            description=base.description,
            content_url=base.content_url or creator.profile_url,
            playable_url=base.playable_url or base.content_url or creator.profile_url,
            thumbnail_url=base.thumbnail_url,
            published_at=datetime.now(timezone.utc),
            is_live=base.is_live if base.is_live is not None else True,
            game=base.game,
            category=base.category,
            viewer_count=base.viewer_count,
            raw_metadata={**(base.raw_metadata or {}), "manual_test": True},
        )

    # Offline / empty feed — still allow verifying Discord webhook delivery.
    is_stream = preferred in {
        ContentEventType.STREAM_STARTED,
        ContentEventType.STREAM_ENDED,
    }
    return NormalizedContentEvent(
        platform=creator.platform,
        event_type=preferred,
        external_content_id=f"manual-test:{subscription_id}:{uuid4()}",
        creator_platform_id=creator.platform_creator_id,
        creator_name=creator.display_name,
        creator_avatar=creator.avatar_url,
        title=f"[Test] {creator.display_name}",
        content_url=creator.profile_url or creator.canonical_url,
        playable_url=creator.profile_url or creator.canonical_url,
        published_at=datetime.now(timezone.utc),
        is_live=True if is_stream else None,
        raw_metadata={"manual_test": True, "synthetic": True},
    )

@router.get("/guilds/{guild_id}/content-notifications/history")
async def delivery_history(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters = [GuildContentSubscription.guild_id == guild_id]
    if platform:
        filters.append(NormalizedContentEventRow.platform == platform)
    if status:
        filters.append(NotificationJob.status == status)

    count_stmt = (
        select(func.count(NotificationJob.id))
        .join(
            GuildContentSubscription,
            GuildContentSubscription.id == NotificationJob.subscription_id,
        )
        .join(
            NormalizedContentEventRow,
            NormalizedContentEventRow.id == NotificationJob.event_id,
        )
        .where(*filters)
    )
    total = int((await session.scalar(count_stmt)) or 0)

    query = (
        select(NotificationJob, GuildContentSubscription, NormalizedContentEventRow)
        .join(
            GuildContentSubscription,
            GuildContentSubscription.id == NotificationJob.subscription_id,
        )
        .join(
            NormalizedContentEventRow,
            NormalizedContentEventRow.id == NotificationJob.event_id,
        )
        .where(*filters)
        .order_by(NotificationJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    rows = (await session.execute(query)).all()
    items = []
    for job, sub, event in rows:
        items.append(
            {
                "job_id": str(job.id),
                "status": job.status,
                "attempt_count": job.attempt_count,
                "latency_ms": job.latency_ms,
                "last_error": job.last_error,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "platform": event.platform,
                "event_type": event.event_type,
                "title": event.title,
                "content_url": event.content_url,
                "creator_name": event.creator_name,
                "destination_channel_id": sub.destination_channel_id,
            }
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/guilds/{guild_id}/content-notifications/analytics")
async def analytics(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    range_start = now - timedelta(days=days)
    guild_join = (
        GuildContentSubscription,
        GuildContentSubscription.id == NotificationJob.subscription_id,
    )
    guild_scope = GuildContentSubscription.guild_id == guild_id

    total = await session.scalar(
        select(func.count(NotificationJob.id))
        .join(*guild_join)
        .where(guild_scope)
    )
    succeeded = await session.scalar(
        select(func.count(NotificationJob.id))
        .join(*guild_join)
        .where(guild_scope, NotificationJob.status == "succeeded")
    )
    failed = await session.scalar(
        select(func.count(NotificationJob.id))
        .join(*guild_join)
        .where(guild_scope, NotificationJob.status.in_(["failed", "dead"]))
    )
    avg_latency = await session.scalar(
        select(func.avg(NotificationJob.latency_ms))
        .join(*guild_join)
        .where(guild_scope, NotificationJob.latency_ms.is_not(None))
    )
    platform_rows = (
        await session.execute(
            select(
                NormalizedContentEventRow.platform,
                func.count(NotificationJob.id),
            )
            .join(
                NotificationJob,
                NotificationJob.event_id == NormalizedContentEventRow.id,
            )
            .join(*guild_join)
            .where(guild_scope)
            .group_by(NormalizedContentEventRow.platform)
        )
    ).all()
    event_type_rows = (
        await session.execute(
            select(
                NormalizedContentEventRow.event_type,
                func.count(NotificationJob.id),
            )
            .join(
                NotificationJob,
                NotificationJob.event_id == NormalizedContentEventRow.id,
            )
            .join(*guild_join)
            .where(guild_scope)
            .group_by(NormalizedContentEventRow.event_type)
        )
    ).all()
    status_rows = (
        await session.execute(
            select(NotificationJob.status, func.count(NotificationJob.id))
            .join(*guild_join)
            .where(guild_scope)
            .group_by(NotificationJob.status)
        )
    ).all()
    day_expr = func.date_trunc("day", NotificationJob.created_at)
    series_rows = (
        await session.execute(
            select(
                day_expr.label("day"),
                func.count(NotificationJob.id)
                .filter(NotificationJob.status == "succeeded")
                .label("succeeded"),
                func.count(NotificationJob.id)
                .filter(NotificationJob.status.in_(["failed", "dead"]))
                .label("failed"),
            )
            .join(*guild_join)
            .where(
                guild_scope,
                NotificationJob.created_at >= range_start,
            )
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()
    failure_rows = (
        await session.execute(
            select(
                NotificationJob.last_error,
                NotificationJob.created_at,
                NormalizedContentEventRow.platform,
            )
            .join(*guild_join)
            .join(
                NormalizedContentEventRow,
                NormalizedContentEventRow.id == NotificationJob.event_id,
            )
            .where(
                guild_scope,
                NotificationJob.status.in_(["failed", "dead"]),
                NotificationJob.last_error.is_not(None),
            )
            .order_by(NotificationJob.created_at.desc())
            .limit(5)
        )
    ).all()

    success_rate = (
        float(succeeded or 0) / float(total) if total else 0.0
    )
    return {
        "notifications_sent": int(succeeded or 0),
        "failed_notifications": int(failed or 0),
        "total_jobs": int(total or 0),
        "delivery_success_rate": round(success_rate, 4),
        "average_delivery_latency_ms": int(avg_latency or 0),
        "platform_distribution": [
            {"platform": platform, "count": int(count)}
            for platform, count in platform_rows
        ],
        "event_type_distribution": [
            {"event_type": event_type, "count": int(count)}
            for event_type, count in event_type_rows
        ],
        "status_distribution": [
            {"status": status, "count": int(count)}
            for status, count in status_rows
        ],
        "series": [
            {
                "day": day.date().isoformat() if hasattr(day, "date") else str(day)[:10],
                "succeeded": int(ok or 0),
                "failed": int(bad or 0),
            }
            for day, ok, bad in series_rows
        ],
        "recent_failures": [
            {
                "last_error": (error or "")[:240],
                "created_at": created.isoformat() if created else None,
                "platform": plat,
            }
            for error, created, plat in failure_rows
        ],
        "range_start": range_start.isoformat(),
        "range_end": now.isoformat(),
        "worker_online": await worker_online(),
    }


def _default_event_types(platform: PlatformType) -> list[str]:
    mapping = {
        PlatformType.YOUTUBE: [ContentEventType.VIDEO_PUBLISHED.value],
        PlatformType.TWITCH: [ContentEventType.STREAM_STARTED.value],
        PlatformType.KICK: [ContentEventType.STREAM_STARTED.value],
        PlatformType.X: [ContentEventType.POST_PUBLISHED.value],
        PlatformType.TIKTOK: [ContentEventType.VIDEO_PUBLISHED.value],
    }
    return mapping.get(platform, [])


def _transport_for(platform: PlatformType) -> str:
    return {
        PlatformType.YOUTUBE: "websub",
        PlatformType.TWITCH: "eventsub",
        PlatformType.KICK: "kick_events",
        PlatformType.X: "poll",
        PlatformType.TIKTOK: "poll",
    }[platform]


async def _ensure_default_template(
    session: AsyncSession,
    guild_id: str,
    platform: PlatformType,
) -> UUID:
    existing = await session.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.guild_id == guild_id,
            NotificationTemplate.platform_default_for == platform.value,
        )
    )
    if existing:
        return existing.id
    row = NotificationTemplate(
        guild_id=guild_id,
        name=f"Default {platform.value.title()}",
        platform_default_for=platform.value,
        content=DEFAULT_TEMPLATES[platform],
        embed_json=default_embed_json(platform),
    )
    session.add(row)
    await session.flush()
    return row.id
