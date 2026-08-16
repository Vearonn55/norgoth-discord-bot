"""Kick official Events API adapter."""

from __future__ import annotations

import base64
import logging
import os
import time
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
        self._token_expires_at: float = 0.0
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

    def _invalidate_token(self) -> None:
        self._token = None
        self._token_expires_at = 0.0

    async def _app_token(self, *, force_refresh: bool = False) -> str:
        now = time.time()
        if (
            not force_refresh
            and self._token
            and now < (self._token_expires_at - 60)
        ):
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
                    # App tokens inherit portal scopes; request explicitly when allowed.
                    "scope": "events:subscribe channel:read",
                },
            )
            if response.status_code != 200:
                # Some Kick apps reject explicit scope on client_credentials — retry bare.
                response = await client.post(
                    KICK_TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id(),
                        "client_secret": self._client_secret(),
                    },
                )
            if response.status_code != 200:
                self._invalidate_token()
                raise PlatformAdapterError(
                    f"Kick token request failed: HTTP {response.status_code}",
                    code="auth_error",
                )
            payload = response.json()
            self._token = str(payload["access_token"])
            expires_in = int(payload.get("expires_in") or 3600)
            self._token_expires_at = now + max(expires_in, 60)
            return self._token
        finally:
            if owns:
                await client.aclose()

    async def _headers(self, *, force_refresh: bool = False) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {await self._app_token(force_refresh=force_refresh)}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Perform an authenticated Kick API call, refreshing once on 401."""

        owns = self._http is None
        client = self._client()
        try:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers=await self._headers(),
            )
            if response.status_code == 401:
                self._invalidate_token()
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=await self._headers(force_refresh=True),
                )
            return response
        finally:
            if owns:
                await client.aclose()

    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        if not self.is_available():
            raise PlatformAdapterError(self.availability_reason() or "Kick unavailable")

        slug = self._extract_slug(input_url)
        response = await self._request(
            "GET",
            f"{KICK_API}/channels",
            params={"slug": slug},
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
        avatar = channel.get("profile_picture")
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

    def _extract_slug(self, value: str) -> str:
        cleaned = value.strip()
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        if parsed.hostname and "kick.com" in parsed.hostname.lower():
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return parts[0].lower()
        return cleaned.strip("/").lower()

    async def subscribe(self, creator: ResolvedCreator) -> dict[str, Any] | None:
        try:
            broadcaster_id = int(creator.platform_creator_id)
        except (TypeError, ValueError):
            logger.warning(
                "Kick subscribe skipped: invalid broadcaster id %r",
                creator.platform_creator_id,
            )
            return None
        response = await self._request(
            "POST",
            f"{KICK_API}/events/subscriptions",
            json={
                "broadcaster_user_id": broadcaster_id,
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

    async def unsubscribe(self, creator: ResolvedCreator) -> None:
        """Delete Kick event subscriptions for this broadcaster when possible."""

        if not self.is_available():
            return
        try:
            broadcaster_id = int(creator.platform_creator_id)
        except (TypeError, ValueError):
            return
        try:
            listed = await self._request(
                "GET",
                f"{KICK_API}/events/subscriptions",
                params={"broadcaster_user_id": broadcaster_id},
            )
            if listed.status_code != 200:
                return
            data = listed.json().get("data") or []
            if not isinstance(data, list):
                return
            ids = [str(row.get("id")) for row in data if row.get("id")]
            if not ids:
                return
            # Kick DELETE accepts repeated `id` query params.
            owns = self._http is None
            client = self._client()
            try:
                await client.request(
                    "DELETE",
                    f"{KICK_API}/events/subscriptions",
                    params=[("id", sub_id) for sub_id in ids],
                    headers=await self._headers(),
                )
            finally:
                if owns:
                    await client.aclose()
        except Exception:  # noqa: BLE001
            logger.exception("Kick event unsubscribe failed")

    async def fetch_latest(
        self,
        creator: ResolvedCreator,
        *,
        limit: int = 5,
    ) -> list[NormalizedContentEvent]:
        """Return the creator's current live stream, if any.

        Prefers ``GET /channels?broadcaster_user_id=`` (includes nested
        ``stream.is_live``) and falls back to ``GET /users/livestreams``.
        """

        if not self.is_available():
            return []
        try:
            broadcaster_id = int(creator.platform_creator_id)
        except (TypeError, ValueError):
            return []

        channel_event = await self._fetch_live_from_channel(creator, broadcaster_id)
        if channel_event is not None:
            return [channel_event]

        return await self._fetch_live_from_users_livestreams(
            creator, broadcaster_id, limit=limit
        )

    async def _fetch_live_from_channel(
        self,
        creator: ResolvedCreator,
        broadcaster_id: int,
    ) -> NormalizedContentEvent | None:
        response = await self._request(
            "GET",
            f"{KICK_API}/channels",
            params={"broadcaster_user_id": broadcaster_id},
        )
        if response.status_code != 200:
            logger.warning(
                "Kick channel livestream lookup failed: %s %s",
                response.status_code,
                response.text[:300],
            )
            return None
        data = response.json().get("data") or []
        if isinstance(data, dict):
            data = [data]
        if not data:
            return None
        channel = data[0]
        stream = channel.get("stream") if isinstance(channel.get("stream"), dict) else {}
        if not stream.get("is_live"):
            return None

        started = stream.get("start_time") or stream.get("started_at")
        stream_key = stream.get("key") or started or "live"
        content_id = f"{creator.platform_creator_id}:{stream_key}"
        slug = channel.get("slug") or creator.username
        profile = f"https://kick.com/{slug}" if slug else creator.profile_url
        category = channel.get("category") if isinstance(channel.get("category"), dict) else {}
        return NormalizedContentEvent(
            platform=PlatformType.KICK,
            event_type=ContentEventType.STREAM_STARTED,
            external_content_id=content_id,
            creator_platform_id=creator.platform_creator_id,
            creator_name=creator.display_name,
            creator_avatar=creator.avatar_url or stream.get("thumbnail"),
            title=channel.get("stream_title") or channel.get("title") or "Live on Kick",
            content_url=stream.get("url") or profile,
            playable_url=stream.get("url") or profile,
            thumbnail_url=stream.get("thumbnail"),
            is_live=True,
            game=category.get("name"),
            viewer_count=stream.get("viewer_count"),
            published_at=datetime.now(timezone.utc),
            raw_metadata={"channel": channel, "stream": stream},
        )

    async def _fetch_live_from_users_livestreams(
        self,
        creator: ResolvedCreator,
        broadcaster_id: int,
        *,
        limit: int,
    ) -> list[NormalizedContentEvent]:
        response = await self._request(
            "GET",
            f"{KICK_API}/users/livestreams",
            params={"user_id": broadcaster_id},
        )
        if response.status_code != 200:
            # Fall back to deprecated v1 livestreams filter.
            response = await self._request(
                "GET",
                f"{KICK_API}/livestreams",
                params={"broadcaster_user_id": broadcaster_id},
            )
            if response.status_code != 200:
                logger.warning(
                    "Kick livestream lookup failed: %s %s",
                    response.status_code,
                    response.text[:300],
                )
                return []

        data = response.json().get("data") or []
        if isinstance(data, dict):
            data = [data]
        events: list[NormalizedContentEvent] = []
        for stream in data[:limit]:
            event = self._normalize_livestream_payload(creator, stream)
            if event is not None:
                events.append(event)
        return events

    def _normalize_livestream_payload(
        self,
        creator: ResolvedCreator,
        stream: dict[str, Any],
    ) -> NormalizedContentEvent | None:
        # v1 LivestreamWithCategory has no is_live — presence means live.
        # Nested v2 payloads may include broadcaster_user / channel objects.
        if stream.get("is_live") is False:
            return None

        broadcaster_user = (
            stream.get("broadcaster_user")
            if isinstance(stream.get("broadcaster_user"), dict)
            else {}
        )
        channel = (
            stream.get("channel") if isinstance(stream.get("channel"), dict) else {}
        )
        category = (
            stream.get("category") if isinstance(stream.get("category"), dict) else {}
        )
        slug = channel.get("slug") or stream.get("slug") or creator.username
        profile = f"https://kick.com/{slug}" if slug else creator.profile_url
        started = stream.get("started_at") or stream.get("start_time")
        stream_id = str(
            stream.get("id")
            or stream.get("channel_id")
            or started
            or stream.get("stream_title")
            or stream.get("title")
            or "live"
        )
        content_id = f"{creator.platform_creator_id}:{stream_id}"
        title = (
            stream.get("title")
            or stream.get("stream_title")
            or stream.get("session_title")
            or "Live on Kick"
        )
        return NormalizedContentEvent(
            platform=PlatformType.KICK,
            event_type=ContentEventType.STREAM_STARTED,
            external_content_id=content_id,
            creator_platform_id=creator.platform_creator_id,
            creator_name=broadcaster_user.get("username") or creator.display_name,
            creator_avatar=(
                broadcaster_user.get("profile_picture")
                or stream.get("profile_picture")
                or creator.avatar_url
            ),
            title=title,
            content_url=profile,
            playable_url=profile,
            thumbnail_url=stream.get("thumbnail"),
            is_live=True,
            game=category.get("name") or stream.get("category_name"),
            viewer_count=stream.get("viewer_count"),
            published_at=datetime.now(timezone.utc),
            raw_metadata=stream,
        )

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
        event_out = NormalizedContentEvent(
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
        if is_live:
            try:
                latest = await self.fetch_latest(
                    ResolvedCreator(
                        platform=PlatformType.KICK,
                        platform_creator_id=creator_id,
                        username=username or name,
                        display_name=name,
                        profile_url=profile
                        or f"https://kick.com/{username or creator_id}",
                        avatar_url=broadcaster.get("profile_picture"),
                    ),
                    limit=1,
                )
            except Exception:
                logger.warning(
                    "cn_metadata_enrich_failed platform=kick creator_id=%s",
                    creator_id,
                    exc_info=True,
                )
                latest = []
            if latest:
                live = latest[0]
                if live.thumbnail_url:
                    event_out.thumbnail_url = live.thumbnail_url
                if live.title:
                    event_out.title = live.title
                if live.game:
                    event_out.game = live.game
                if live.viewer_count is not None:
                    event_out.viewer_count = live.viewer_count
                if live.content_url:
                    event_out.content_url = live.content_url
                    event_out.playable_url = live.playable_url or live.content_url
        return event_out

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
