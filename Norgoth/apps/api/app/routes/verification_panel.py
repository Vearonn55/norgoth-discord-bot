"""Publish or update a Discord verification panel with a browser link button."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.guild import Guild
from app.repositories.configuration_repository import ConfigurationRepository
from app.services.campaign_store import now_iso
from app.services.configuration_service import ConfigurationService
from app.services.verification_setup import (
    derive_verification_setup_state,
    has_required_bindings,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Verification Panel"],
    dependencies=[Depends(guild_manager_dependency())],
)

DISCORD_API_BASE_URL = "https://discord.com/api/v10"
SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"


class PublishVerificationPanelRequest(BaseModel):
    channel_id: str = Field(pattern=SNOWFLAKE_PATTERN)
    title: str = Field(default="Verify to join", max_length=256)
    description: str = Field(
        default=(
            "Click the button below to open verification in your browser. "
            "Complete Discord OAuth to receive your member roles."
        ),
        max_length=2000,
    )
    lang: str = Field(default="en", max_length=8)


@router.post("/guilds/{guild_id}/verification/publish-panel")
async def publish_verification_panel(
    guild_id: str,
    payload: PublishVerificationPanelRequest,
) -> dict[str, Any]:
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="DISCORD_BOT_TOKEN is not configured in Norgoth/.env.",
        )

    settings = get_settings()

    if (
        settings.discord_client_id is None
        or settings.discord_client_secret is None
        or settings.discord_redirect_uri is None
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Discord OAuth is not configured. Set NORGOTH_DISCORD_CLIENT_ID, "
                "NORGOTH_DISCORD_CLIENT_SECRET, and NORGOTH_DISCORD_REDIRECT_URI."
            ),
        )

    existing_message_id: str | None = None

    try:
        factory = get_session_factory()
        async with factory() as session:
            guild = (
                await session.execute(
                    select(Guild).where(Guild.discord_guild_id == str(guild_id))
                )
            ).scalar_one_or_none()
            if guild is None:
                raise HTTPException(status_code=404, detail="Discord guild not found.")
            configuration = await ConfigurationService(
                ConfigurationRepository(session)
            ).get_by_guild_id(guild.id)
            setup = derive_verification_setup_state(configuration)
            if configuration is None or not has_required_bindings(configuration):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "verification_setup_incomplete",
                        "message": (
                            "Save verification channels and roles before publishing "
                            "the Discord panel."
                        ),
                        "setup_state": setup.state,
                    },
                )
            if (
                configuration.verification_channel_id
                and configuration.verification_channel_id != payload.channel_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "verification_channel_mismatch",
                        "message": (
                            "Publish channel must match the saved verification "
                            "channel."
                        ),
                    },
                )
            existing_message_id = configuration.panel_message_id
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not load verification configuration: {error}",
        ) from error

    api_base = (
        os.getenv("NORGOTH_PUBLIC_API_URL", "").strip()
        or os.getenv("NORGOTH_API_URL", "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")

    locale = payload.lang if payload.lang in {"en", "tr"} else "en"
    verify_url = (
        f"{api_base}/api/v1/oauth/discord/authorize/{guild_id}?lang={locale}"
    )

    message_payload = {
        "embeds": [
            {
                "title": payload.title,
                "description": payload.description,
                "color": 0x57F287,
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Verify in browser",
                        "url": verify_url,
                    }
                ],
            }
        ],
    }

    headers = {"Authorization": f"Bot {bot_token}"}
    updated = False
    message_id: str | None = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        if existing_message_id:
            try:
                edit_response = await client.patch(
                    (
                        f"{DISCORD_API_BASE_URL}/channels/{payload.channel_id}"
                        f"/messages/{existing_message_id}"
                    ),
                    headers=headers,
                    json=message_payload,
                )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "verification_panel_publish_failed",
                        "message": f"Could not reach Discord: {error}",
                    },
                ) from error

            if edit_response.status_code == 200:
                updated = True
                message_id = str(
                    (edit_response.json() or {}).get("id") or existing_message_id
                )
            elif edit_response.status_code != 404:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "verification_panel_publish_failed",
                        "message": (
                            "Discord rejected the verification panel update "
                            f"(HTTP {edit_response.status_code}): "
                            f"{edit_response.text[:200]}"
                        ),
                    },
                )
            # 404 → recreate below

        if message_id is None:
            try:
                response = await client.post(
                    f"{DISCORD_API_BASE_URL}/channels/{payload.channel_id}/messages",
                    headers=headers,
                    json=message_payload,
                )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "verification_panel_publish_failed",
                        "message": f"Could not reach Discord: {error}",
                    },
                ) from error

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "verification_panel_publish_failed",
                        "message": (
                            "Discord rejected the verification panel "
                            f"(HTTP {response.status_code}): {response.text[:200]}"
                        ),
                    },
                )
            body = response.json() or {}
            message_id = str(body.get("id") or "").strip() or None

    if not message_id:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "verification_panel_publish_failed",
                "message": "Discord did not return a panel message id.",
            },
        )

    try:
        factory = get_session_factory()
        async with factory() as session:
            guild = (
                await session.execute(
                    select(Guild).where(Guild.discord_guild_id == str(guild_id))
                )
            ).scalar_one_or_none()
            if guild is None:
                raise HTTPException(status_code=404, detail="Discord guild not found.")
            settings_row = await ConfigurationRepository(session).get_settings(
                guild.id
            )
            if settings_row is None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "verification_setup_incomplete",
                        "message": "Verification settings are missing.",
                    },
                )
            settings_row.panel_message_id = message_id
            await session.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "verification_panel_message_id_persist_failed guild_id=%s "
            "channel_id=%s message_id=%s",
            guild_id,
            payload.channel_id,
            message_id,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "verification_panel_publish_failed",
                "message": (
                    "Panel was published in Discord but the message id could "
                    "not be saved. Retry Save to reconcile."
                ),
            },
        )

    return {
        "ok": True,
        "channel_id": payload.channel_id,
        "message_id": message_id,
        "updated": updated,
        "verify_url": verify_url,
        "published_at": now_iso(),
    }
