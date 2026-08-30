"""Twitch EventSub + Helix adapter."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.integrations.content_platforms.base import ContentPlatformAdapter
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformAdapterError,
    PlatformRawEvent,
    PlatformType,
    ResolvedCreator,
)

logger = logging.getLogger("norgoth.content.twitch")

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_API = "https://api.twitch.tv/helix"


class TwitchAdapter(ContentPlatformAdapter):
    platform = PlatformType.TWITCH

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client
        self._token: str | None = None

    def supports_push(self) -> bool:
        return True

    def is_available(self) -> bool:
        return bool(self._client_id() and self._client_secret())

    def availability_reason(self) -> str | None:
        if self.is_available():
            return None
        return "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required."

    def _client_id(self) -> str:
        return os.getenv("TWITCH_CLIENT_ID", "").strip()

    def _client_secret(self) -> str:
        return os.getenv("TWITCH_CLIENT_SECRET", "").strip()

    def _client(self) -> httpx.AsyncClient:
        return self._http or httpx.AsyncClient(timeout=20.0)

    async def _app_token(self) -> str:
        if self._token:
            return self._token
        owns = self._http is None
        client = self._client()
        try:
            response = await client.post(
                TWITCH_TOKEN_URL,
                params={
                    "client_id": self._client_id(),
                    "client_secret": self._client_secret(),
                    "grant_type": "client_credentials",
                },
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
            return self._token
        finally:
            if owns:
                await client.aclose()

    async def _headers(self) -> dict[str, str]:
        token = await self._app_token()
        return {
            "Client-ID": self._client_id(),
            "Authorization": f"Bearer {token}",
        }

    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        if not self.is_available():
            raise PlatformAdapterError(self.availability_reason() or "Twitch unavailable")

        login = self._extract_login(input_url)
        owns = self._http is None
        client = self._client()
        try:
            response = await client.get(
                f"{TWITCH_API}/users",
                params={"login": login},
                headers=await self._headers(),
            )
            if response.status_code != 200:
                raise PlatformAdapterError(
                    f"Twitch user lookup failed: HTTP {response.status_code}",
                    code="resolve_failed",
                )
            items = response.json().get("data") or []
            if not items:
                raise PlatformAdapterError("Twitch user not found.", code="not_found")
            user = items[0]
            return ResolvedCreator(
                platform=PlatformType.TWITCH,
                platform_creator_id=str(user["id"]),
                username=user.get("login") or login,
                display_name=user.get("display_name") or login,
                profile_url=f"https://www.twitch.tv/{user.get('login') or login}",
                avatar_url=user.get("profile_image_url"),
                canonical_url=f"https://www.twitch.tv/{user.get('login') or login}",
            )
        finally:
            if owns:
                await client.aclose()

    def _extract_login(self, value: str) -> str:
        cleaned = value.strip()
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        if parsed.hostname and "twitch.tv" in parsed.hostname.lower():
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return parts[0].lower()
        return cleaned.strip("/").lower()

    async def subscribe(self, creator: ResolvedCreator) -> dict[str, Any] | None:
        callback = os.getenv("NORGOTH_PUBLIC_API_URL", "").rstrip("/")
        secret = os.getenv("TWITCH_EVENTSUB_SECRET", "").strip() or os.urandom(16).hex()
        if not callback:
            return None
        owns = self._http is None
        client = self._client()
        try:
            headers = await self._headers()
            transport = {
                "method": "webhook",
                "callback": f"{callback}/webhooks/twitch/eventsub",
                "secret": secret,
            }
            subscription_ids: list[str] = []
            primary_id: str | None = None
            for event_type in ("stream.online", "stream.offline"):
                response = await client.post(
                    f"{TWITCH_API}/eventsub/subscriptions",
                    headers=headers,
                    json={
                        "type": event_type,
                        "version": "1",
                        "condition": {
                            "broadcaster_user_id": creator.platform_creator_id
                        },
                        "transport": transport,
                    },
                )
                if response.status_code not in {200, 202}:
                    logger.warning(
                        "Twitch EventSub subscribe failed (%s): %s %s",
                        event_type,
                        response.status_code,
                        response.text,
                    )
                    continue
                data = (response.json().get("data") or [{}])[0]
                sub_id = data.get("id")
                if sub_id:
                    subscription_ids.append(str(sub_id))
                    if event_type == "stream.online":
                        primary_id = str(sub_id)
            if not subscription_ids:
                return None
            return {
                "external_subscription_id": primary_id or subscription_ids[0],
                "subscription_ids": subscription_ids,
                "secret": secret,
                "status": "enabled",
            }
        finally:
            if owns:
                await client.aclose()

    async def unsubscribe(self, creator: ResolvedCreator) -> None:
        """Best-effort delete of EventSub rows for this broadcaster."""

        if not self.is_available():
            return
        owns = self._http is None
        client = self._client()
        try:
            headers = await self._headers()
            response = await client.get(
                f"{TWITCH_API}/eventsub/subscriptions",
                headers=headers,
                params={"user_id": creator.platform_creator_id},
            )
            if response.status_code != 200:
                return
            for row in response.json().get("data") or []:
                condition = row.get("condition") or {}
                if str(condition.get("broadcaster_user_id") or "") != str(
                    creator.platform_creator_id
                ):
                    continue
                sub_id = row.get("id")
                if not sub_id:
                    continue
                await client.delete(
                    f"{TWITCH_API}/eventsub/subscriptions",
                    headers=headers,
                    params={"id": sub_id},
                )
        except Exception:  # noqa: BLE001
            logger.exception("Twitch EventSub unsubscribe failed")
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
                f"{TWITCH_API}/streams",
                params={"user_id": creator.platform_creator_id},
                headers=await self._headers(),
            )
            if response.status_code != 200:
                return []
            data = response.json().get("data") or []
            events: list[NormalizedContentEvent] = []
            for stream in data[:limit]:
                events.append(
                    NormalizedContentEvent(
                        platform=PlatformType.TWITCH,
                        event_type=ContentEventType.STREAM_STARTED,
                        external_content_id=str(stream.get("id")),
                        creator_platform_id=creator.platform_creator_id,
                        creator_name=creator.display_name,
                        creator_avatar=creator.avatar_url,
                        title=stream.get("title"),
                        content_url=creator.profile_url,
                        playable_url=creator.profile_url,
                        thumbnail_url=(stream.get("thumbnail_url") or "")
                        .replace("{width}", "1280")
                        .replace("{height}", "720"),
                        is_live=True,
                        game=stream.get("game_name"),
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
        sub_type = str((event.raw.get("subscription") or {}).get("type") or "")
        if sub_type == "stream.offline" or event.event_type == ContentEventType.STREAM_ENDED:
            event_type = ContentEventType.STREAM_ENDED
        elif (
            sub_type == "stream.online"
            or event.event_type == ContentEventType.STREAM_STARTED
        ):
            event_type = ContentEventType.STREAM_STARTED
        else:
            event_type = event.event_type

        event_data = event.raw.get("event") or event.raw
        broadcaster_id = str(
            event_data.get("broadcaster_user_id") or event.platform_creator_id
        )
        login = event_data.get("broadcaster_user_login") or ""
        name = event_data.get("broadcaster_user_name") or login or broadcaster_id
        stream_id = str(event_data.get("id") or event.external_content_id)
        profile_url = f"https://www.twitch.tv/{login}" if login else None

        title = None
        game = None
        viewers = None
        thumb = None
        stream_started_at = None
        if event_type == ContentEventType.STREAM_STARTED and self.is_available():
            latest = await self.fetch_latest(
                ResolvedCreator(
                    platform=PlatformType.TWITCH,
                    platform_creator_id=broadcaster_id,
                    username=login,
                    display_name=name,
                    profile_url=profile_url or f"https://www.twitch.tv/{broadcaster_id}",
                ),
                limit=1,
            )
            if latest:
                title = latest[0].title
                game = latest[0].game
                viewers = latest[0].viewer_count
                thumb = latest[0].thumbnail_url
                stream_id = latest[0].external_content_id
                raw_started = (latest[0].raw_metadata or {}).get("started_at")
                if isinstance(raw_started, str):
                    try:
                        stream_started_at = datetime.fromisoformat(
                            raw_started.replace("Z", "+00:00")
                        )
                    except ValueError:
                        stream_started_at = None

        published = stream_started_at or datetime.now(timezone.utc)
        return NormalizedContentEvent(
            platform=PlatformType.TWITCH,
            event_type=event_type,
            external_content_id=stream_id,
            creator_platform_id=broadcaster_id,
            creator_name=name,
            title=title,
            content_url=profile_url,
            playable_url=profile_url,
            thumbnail_url=thumb,
            is_live=event_type == ContentEventType.STREAM_STARTED,
            game=game,
            viewer_count=viewers,
            published_at=published,
            stream_started_at=stream_started_at or published,
            raw_metadata=event.raw,
        )


def verify_twitch_signature(
    *,
    secret: str,
    message_id: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    message = message_id.encode() + timestamp.encode() + body
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature)
