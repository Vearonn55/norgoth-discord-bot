"""Publish a Discord verification panel with a browser link button."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.services.campaign_store import now_iso

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

    # Prefer public API base; fall back to local API so the link always works in dev.
    api_base = (
        os.getenv("NORGOTH_PUBLIC_API_URL", "").strip()
        or os.getenv("NORGOTH_API_URL", "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")

    verify_url = f"{api_base}/api/v1/oauth/discord/authorize/{guild_id}"

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

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                f"{DISCORD_API_BASE_URL}/channels/{payload.channel_id}/messages",
                headers={"Authorization": f"Bot {bot_token}"},
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
                f"Discord rejected the verification panel "
                f"(HTTP {response.status_code}): {response.text[:200]}"
            ),
        )

    return {
        "ok": True,
        "channel_id": payload.channel_id,
        "verify_url": verify_url,
        "published_at": now_iso(),
    }
