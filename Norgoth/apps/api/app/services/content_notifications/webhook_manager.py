"""Managed Discord webhook create/reuse/execute helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.models.content_notifications import DiscordManagedWebhook
from app.security.secret_box import require_secret_box
from app.integrations.content_platforms.types import WebhookHealth

NORGOTH_WEBHOOK_NAME = "Norgoth Notifications"


class WebhookManagerError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "webhook_error",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


async def ensure_managed_webhook(
    session: AsyncSession,
    bot: DiscordBotClient,
    *,
    guild_id: str,
    channel_id: str,
) -> DiscordManagedWebhook:
    existing = await session.scalar(
        select(DiscordManagedWebhook).where(
            DiscordManagedWebhook.guild_id == guild_id,
            DiscordManagedWebhook.channel_id == channel_id,
        )
    )
    if existing and existing.status == WebhookHealth.HEALTHY:
        return existing

    box = require_secret_box()

    # Prefer reusing an existing Norgoth-named webhook in the channel.
    try:
        webhooks = await bot.list_channel_webhooks(channel_id)
    except DiscordBotAPIError as error:
        raise WebhookManagerError(
            f"Cannot list channel webhooks: {error}",
            code="permission_error",
        ) from error

    match = next(
        (
            wh
            for wh in webhooks
            if isinstance(wh, dict)
            and wh.get("name") == NORGOTH_WEBHOOK_NAME
            and wh.get("token")
        ),
        None,
    )

    if match is None:
        try:
            match = await bot.create_channel_webhook(
                channel_id,
                name=NORGOTH_WEBHOOK_NAME,
                reason="Norgoth content notifications",
            )
        except DiscordBotAPIError as error:
            raise WebhookManagerError(
                f"Cannot create channel webhook: {error}",
                code="permission_error",
            ) from error

    token = match.get("token")
    webhook_id = str(match.get("id") or "")
    if not token or not webhook_id:
        raise WebhookManagerError(
            "Discord webhook response missing id/token.",
            code="invalid",
        )

    encrypted = box.encrypt(str(token))
    now = datetime.now(timezone.utc)

    if existing:
        existing.webhook_id = webhook_id
        existing.encrypted_webhook_token = encrypted
        existing.status = WebhookHealth.HEALTHY
        existing.last_verified_at = now
        await session.flush()
        return existing

    row = DiscordManagedWebhook(
        guild_id=guild_id,
        channel_id=channel_id,
        webhook_id=webhook_id,
        encrypted_webhook_token=encrypted,
        status=WebhookHealth.HEALTHY,
        last_verified_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def execute_managed_webhook(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    webhook_row: DiscordManagedWebhook,
    payload: dict[str, Any],
) -> dict[str, Any]:
    box = require_secret_box()
    try:
        token = box.decrypt(webhook_row.encrypted_webhook_token)
    except Exception as error:  # noqa: BLE001
        webhook_row.status = WebhookHealth.INVALID
        await session.flush()
        raise WebhookManagerError(
            "Stored webhook token could not be decrypted.",
            code="invalid",
        ) from error

    url = (
        f"https://discord.com/api/v10/webhooks/"
        f"{webhook_row.webhook_id}/{token}"
    )
    response = await http_client.post(url, json=payload, params={"wait": "true"})

    if response.status_code in {200, 204}:
        webhook_row.status = WebhookHealth.HEALTHY
        webhook_row.last_verified_at = datetime.now(timezone.utc)
        await session.flush()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    if response.status_code == 404:
        webhook_row.status = WebhookHealth.MISSING
        await session.flush()
        raise WebhookManagerError("Webhook was deleted.", code="missing")

    if response.status_code == 401:
        webhook_row.status = WebhookHealth.INVALID
        await session.flush()
        raise WebhookManagerError("Webhook token invalid.", code="invalid")

    if response.status_code == 429:
        retry_after_raw = response.headers.get("Retry-After") or response.headers.get(
            "retry-after"
        )
        retry_after: float | None = None
        if retry_after_raw:
            try:
                retry_after = float(retry_after_raw)
            except ValueError:
                retry_after = None
        # Discord also returns JSON {"retry_after": seconds} on many routes.
        if retry_after is None:
            try:
                body = response.json()
                if isinstance(body, dict) and body.get("retry_after") is not None:
                    retry_after = float(body["retry_after"])
            except Exception:  # noqa: BLE001
                retry_after = None
        raise WebhookManagerError(
            f"Discord rate limited webhook execute"
            f"{f' (retry_after={retry_after}s)' if retry_after is not None else ''}.",
            code="rate_limited",
            retry_after=retry_after,
        )

    raise WebhookManagerError(
        f"Webhook execute failed: HTTP {response.status_code} {response.text}",
        code=f"http_{response.status_code}",
    )


async def get_webhook_for_channel(
    session: AsyncSession,
    *,
    guild_id: str,
    channel_id: str,
) -> DiscordManagedWebhook | None:
    return await session.scalar(
        select(DiscordManagedWebhook).where(
            DiscordManagedWebhook.guild_id == guild_id,
            DiscordManagedWebhook.channel_id == channel_id,
        )
    )


async def mark_webhook_unhealthy(
    session: AsyncSession,
    webhook_id: UUID,
    status: WebhookHealth,
) -> None:
    row = await session.get(DiscordManagedWebhook, webhook_id)
    if row is None:
        return
    row.status = status
    await session.flush()
