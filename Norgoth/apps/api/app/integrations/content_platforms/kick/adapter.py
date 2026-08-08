"""Kick official Events API adapter."""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.integrations.content_platforms.base import ContentPlatformAdapter
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformAdapterError,
    PlatformRawEvent,
    PlatformType,
    ResolvedCreator,
)

logger = logging.getLogger("norgoth.content.kick")

KICK_TOKEN_URL = "https://id.kick.com/oauth/token"
KICK_API = "https://api.kick.com/public/v1"


class KickAdapter(ContentPlatformAdapter):
    platform = PlatformType.KICK

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client
        self._token: str | None = None
        self._public_key_pem: str | None = None

    def supports_push(self) -> bool:
        return True

    def is_available(self) -> bool:
        return bool(self._client_id() and self._client_secret())

    def availability_reason(self) -> str | None:
        if self.is_available():
            return None
        return "KICK_CLIENT_ID and KICK_CLIENT_SECRET are required."

    def _client_id(self) -> str:
        return os.getenv("KICK_CLIENT_ID", "").strip()

    def _client_secret(self) -> str:
        return os.getenv("KICK_CLIENT_SECRET", "").strip()

    def _client(self) -> httpx.AsyncClient:
        return self._http or httpx.AsyncClient(timeout=20.0)

    async def _app_token(self) -> str:
        if self._token:
            return self._token
        owns = self._http is None
        client = self._client()
        try:
            response = await client.post(
                KICK_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id(),
                    "client_secret": self._client_secret(),
                },
            )
            if response.status_code != 200:
                raise PlatformAdapterError(
                    f"Kick token request failed: HTTP {response.status_code}",
                    code="auth_error",
                )
            self._token = response.json()["access_token"]
            return self._token
        finally:
            if owns:
                await client.aclose()

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._app_token()}"}

    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        if not self.is_available():
            raise PlatformAdapterError(self.availability_reason() or "Kick unavailable")

        slug = self._extract_slug(input_url)
        owns = self._http is None
        client = self._client()
        try:
            response = await client.get(
                f"{KICK_API}/channels",
                params={"slug": slug},
                headers=await self._headers(),
            )
            if response.status_code != 200:
                raise PlatformAdapterError(
                    f"Kick channel lookup failed: HTTP {response.status_code}",
                    code="resolve_failed",
                )
            payload = response.json()
            data = payload.get("data") or payload
            if isinstance(data, list):
                channel = data[0] if data else None
            elif isinstance(data, dict):
                channel = data
            else:
                channel = None
            if not channel:
                raise PlatformAdapterError("Kick channel not found.", code="not_found")

            user_id = str(
                channel.get("broadcaster_user_id")
                or channel.get("user_id")
                or channel.get("id")
            )
            username = channel.get("slug") or slug
            display = (
                channel.get("channel_name")
                or (channel.get("user") or {}).get("name")
                or username
            )
            avatar = channel.get("banner_picture") or channel.get("profile_picture")
            return ResolvedCreator(
                platform=PlatformType.KICK,
                platform_creator_id=user_id,
                username=username,
                display_name=str(display),
                profile_url=f"https://kick.com/{username}",
                avatar_url=avatar,
                canonical_url=f"https://kick.com/{username}",
                metadata={"slug": username},
            )
        finally:
            if owns:
                await client.aclose()

    def _extract_slug(self, value: str) -> str:
        cleaned = value.strip()
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        if parsed.hostname and "kick.com" in parsed.hostname.lower():
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return parts[0].lower()
        return cleaned.strip("/").lower()

    async def subscribe(self, creator: ResolvedCreator) -> dict[str, Any] | None:
        owns = self._http is None
        client = self._client()
        try:
            response = await client.post(
                f"{KICK_API}/events/subscriptions",
                headers=await self._headers(),
                json={
                    "broadcaster_user_id": int(creator.platform_creator_id),
                    "events": [
                        {"name": "livestream.status.updated", "version": 1},
                    ],
                    "method": "webhook",
                },
            )
            if response.status_code not in {200, 201}:
                logger.warning(
                    "Kick event subscribe failed: %s %s",
                    response.status_code,
                    response.text,
                )
                return None
            data = response.json().get("data") or response.json()
            sub_id = None
            if isinstance(data, list) and data:
                sub_id = data[0].get("id")
            elif isinstance(data, dict):
                sub_id = data.get("id")
            return {"external_subscription_id": sub_id}
        finally:
            if owns:
                await client.aclose()

    async def fetch_latest(
        self,
        creator: ResolvedCreator,
        *,
        limit: int = 5,
    ) -> list[NormalizedContentEvent]:
        if not self.is_available():
            return []
        owns = self._http is None
        client = self._client()
        try:
            response = await client.get(
                f"{KICK_API}/livestreams",
                params={"broadcaster_user_id": creator.platform_creator_id},
                headers=await self._headers(),
            )
            if response.status_code != 200:
                return []
            data = response.json().get("data") or []
            if isinstance(data, dict):
                data = [data]
            events: list[NormalizedContentEvent] = []
            for stream in data[:limit]:
                if not stream.get("is_live", True):
                    continue
                stream_id = str(stream.get("id") or stream.get("session_title") or "live")
                events.append(
                    NormalizedContentEvent(
                        platform=PlatformType.KICK,
                        event_type=ContentEventType.STREAM_STARTED,
                        external_content_id=stream_id,
                        creator_platform_id=creator.platform_creator_id,
                        creator_name=creator.display_name,
                        creator_avatar=creator.avatar_url,
                        title=stream.get("session_title") or stream.get("title"),
                        content_url=creator.profile_url,
                        playable_url=creator.profile_url,
                        thumbnail_url=stream.get("thumbnail"),
                        is_live=True,
                        game=(stream.get("category") or {}).get("name")
                        if isinstance(stream.get("category"), dict)
                        else stream.get("category_name"),
                        viewer_count=stream.get("viewer_count"),
                        published_at=datetime.now(timezone.utc),
                        raw_metadata=stream,
                    )
                )
            return events
        finally:
            if owns:
                await client.aclose()

    async def enrich_event(self, event: PlatformRawEvent) -> NormalizedContentEvent:
        raw = event.raw
        is_live = bool(raw.get("is_live"))
        broadcaster = raw.get("broadcaster") or {}
        creator_id = str(
            broadcaster.get("user_id") or event.platform_creator_id
        )
        username = broadcaster.get("channel_slug") or broadcaster.get("username") or ""
        name = broadcaster.get("username") or username or creator_id
        profile = f"https://kick.com/{username}" if username else None
        content_id = (
            f"{creator_id}:{raw.get('started_at') or event.external_content_id}"
        )
        return NormalizedContentEvent(
            platform=PlatformType.KICK,
            event_type=(
                ContentEventType.STREAM_STARTED
                if is_live
                else ContentEventType.STREAM_ENDED
            ),
            external_content_id=content_id,
            creator_platform_id=creator_id,
            creator_name=name,
            creator_avatar=broadcaster.get("profile_picture"),
            title=raw.get("title"),
            content_url=profile,
            playable_url=profile,
            is_live=is_live,
            published_at=datetime.now(timezone.utc),
            raw_metadata=raw,
        )

    async def get_public_key(self) -> str:
        if self._public_key_pem:
            return self._public_key_pem
        owns = self._http is None
        client = self._client()
        try:
            response = await client.get(f"{KICK_API}/public-key")
            response.raise_for_status()
            data = response.json().get("data") or response.json()
            pem = data.get("public_key") if isinstance(data, dict) else None
            if not pem:
                raise PlatformAdapterError("Kick public key missing.")
            self._public_key_pem = pem
            return pem
        finally:
            if owns:
                await client.aclose()


async def verify_kick_signature(
    *,
    message_id: str,
    timestamp: str,
    body: bytes,
    signature_b64: str,
    public_key_pem: str,
) -> bool:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        signed = f"{message_id}.{timestamp}.{body.decode('utf-8')}".encode()
        signature = base64.b64decode(signature_b64)
        public_key.verify(  # type: ignore[attr-defined]
            signature,
            signed,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Kick signature verification failed")
        return False
