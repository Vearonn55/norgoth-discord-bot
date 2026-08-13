"""YouTube content platform adapter (WebSub + Atom + optional Data API)."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

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

logger = logging.getLogger("norgoth.content.youtube")

CHANNEL_ID_RE = re.compile(r"^UC[\w-]{20,}$")
HANDLE_RE = re.compile(r"^@?[\w.-]{3,30}$")
ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def _youtube_api_key() -> str | None:
    return os.getenv("YOUTUBE_API_KEY", "").strip() or None


class YouTubeAdapter(ContentPlatformAdapter):
    platform = PlatformType.YOUTUBE

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client

    def _client(self) -> httpx.AsyncClient:
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(timeout=20.0)

    def supports_push(self) -> bool:
        return True

    def is_available(self) -> bool:
        return bool(_youtube_api_key())

    def availability_reason(self) -> str | None:
        if self.is_available():
            return None
        return "YOUTUBE_API_KEY is required for official channel resolve and enrichment."

    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        if not self.is_available():
            raise PlatformAdapterError(
                self.availability_reason() or "YouTube unavailable",
                code="platform_unavailable",
            )
        raw = input_url.strip()
        channel_id = self._extract_channel_id(raw)
        handle = None

        if channel_id is None:
            handle = self._extract_handle(raw)
            if handle is None:
                raise PlatformAdapterError(
                    "Unrecognized YouTube URL or channel id.",
                    code="invalid_url",
                )
            channel_id = await self._resolve_handle(handle)

        profile = await self._fetch_channel_profile(channel_id)
        return ResolvedCreator(
            platform=PlatformType.YOUTUBE,
            platform_creator_id=channel_id,
            username=profile.get("customUrl") or handle or channel_id,
            display_name=profile.get("title") or handle or channel_id,
            profile_url=f"https://www.youtube.com/channel/{channel_id}",
            avatar_url=profile.get("avatar_url"),
            canonical_url=f"https://www.youtube.com/channel/{channel_id}",
            metadata={"handle": handle},
        )

    def _extract_channel_id(self, value: str) -> str | None:
        if CHANNEL_ID_RE.match(value):
            return value
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = (parsed.hostname or "").lower()
        if "youtube.com" not in host and "youtu.be" not in host:
            return None
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "channel" and CHANNEL_ID_RE.match(parts[1]):
            return parts[1]
        return None

    def _extract_handle(self, value: str) -> str | None:
        if HANDLE_RE.match(value) and value.startswith("@"):
            return value if value.startswith("@") else f"@{value}"
        parsed = urlparse(value if "://" in value else f"https://{value}")
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0].startswith("@") and HANDLE_RE.match(parts[0]):
            return parts[0]
        if parts and parts[0] in {"c", "user"} and len(parts) >= 2:
            return parts[1]
        return None

    async def _resolve_handle(self, handle: str) -> str:
        api_key = _youtube_api_key()
        if not api_key:
            raise PlatformAdapterError(
                "YOUTUBE_API_KEY is required to resolve YouTube handles.",
                code="platform_unavailable",
            )
        owns_client = self._http is None
        client = self._client()
        try:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "id",
                    "forHandle": handle.lstrip("@"),
                    "key": api_key,
                },
            )
            if response.status_code == 200:
                items = response.json().get("items") or []
                if items:
                    return items[0]["id"]
            raise PlatformAdapterError(
                "Could not resolve YouTube handle via Data API.",
                code="resolve_failed",
            )
        finally:
            if owns_client:
                await client.aclose()

    async def _fetch_channel_profile(self, channel_id: str) -> dict[str, Any]:
        api_key = _youtube_api_key()
        if not api_key:
            return {"title": channel_id}
        owns_client = self._http is None
        client = self._client()
        try:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "snippet",
                    "id": channel_id,
                    "key": api_key,
                },
            )
            if response.status_code != 200:
                return {"title": channel_id}
            items = response.json().get("items") or []
            if not items:
                return {"title": channel_id}
            snippet = items[0].get("snippet") or {}
            thumbs = snippet.get("thumbnails") or {}
            avatar = (
                (thumbs.get("high") or {}).get("url")
                or (thumbs.get("default") or {}).get("url")
            )
            return {
                "title": snippet.get("title") or channel_id,
                "customUrl": snippet.get("customUrl"),
                "avatar_url": avatar,
            }
        finally:
            if owns_client:
                await client.aclose()

    async def subscribe(self, creator: ResolvedCreator) -> dict[str, Any] | None:
        callback = os.getenv("NORGOTH_PUBLIC_API_URL", "").rstrip("/")
        if not callback:
            return None
        hub = "https://pubsubhubbub.appspot.com/subscribe"
        topic = (
            f"https://www.youtube.com/feeds/videos.xml"
            f"?channel_id={creator.platform_creator_id}"
        )
        owns_client = self._http is None
        client = self._client()
        try:
            response = await client.post(
                hub,
                data={
                    "hub.callback": f"{callback}/webhooks/youtube/websub",
                    "hub.mode": "subscribe",
                    "hub.topic": topic,
                    "hub.verify": "async",
                    "hub.lease_seconds": "432000",
                },
            )
            if response.status_code not in {202, 204}:
                logger.warning(
                    "YouTube WebSub subscribe failed: %s %s",
                    response.status_code,
                    response.text,
                )
                return None
            return {"topic": topic, "hub": hub, "status_code": response.status_code}
        finally:
            if owns_client:
                await client.aclose()

    async def fetch_latest(
        self,
        creator: ResolvedCreator,
        *,
        limit: int = 5,
    ) -> list[NormalizedContentEvent]:
        url = (
            "https://www.youtube.com/feeds/videos.xml"
            f"?channel_id={creator.platform_creator_id}"
        )
        owns_client = self._http is None
        client = self._client()
        try:
            response = await client.get(url)
            response.raise_for_status()
            return parse_atom_feed(
                response.text,
                creator=creator,
                limit=limit,
            )
        finally:
            if owns_client:
                await client.aclose()

    async def enrich_event(self, event: PlatformRawEvent) -> NormalizedContentEvent:
        creator_id = event.platform_creator_id
        video_id = event.external_content_id
        title = event.raw.get("title")
        published = event.raw.get("published")
        content_url = event.raw.get("content_url") or f"https://youtu.be/{video_id}"
        thumbnail = event.raw.get("thumbnail_url") or (
            f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        )
        is_live = None
        event_type = event.event_type

        api_key = _youtube_api_key()
        if api_key:
            owns_client = self._http is None
            client = self._client()
            try:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "snippet,liveStreamingDetails",
                        "id": video_id,
                        "key": api_key,
                    },
                )
                if response.status_code == 200:
                    items = response.json().get("items") or []
                    if items:
                        snippet = items[0].get("snippet") or {}
                        title = snippet.get("title") or title
                        live = items[0].get("liveStreamingDetails") or {}
                        if live.get("actualStartTime") and not live.get("actualEndTime"):
                            is_live = True
                            event_type = ContentEventType.STREAM_STARTED
                        elif snippet.get("liveBroadcastContent") == "live":
                            is_live = True
                            event_type = ContentEventType.STREAM_STARTED
            finally:
                if owns_client:
                    await client.aclose()

        published_at = None
        if isinstance(published, str):
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                published_at = None

        return NormalizedContentEvent(
            platform=PlatformType.YOUTUBE,
            event_type=event_type,
            external_content_id=video_id,
            creator_platform_id=creator_id,
            creator_name=str(event.raw.get("creator_name") or creator_id),
            creator_avatar=event.raw.get("creator_avatar"),
            title=title,
            content_url=content_url,
            playable_url=content_url,
            thumbnail_url=thumbnail,
            published_at=published_at,
            is_live=is_live,
            raw_metadata=event.raw,
        )


def parse_atom_feed(
    xml_text: str,
    *,
    creator: ResolvedCreator,
    limit: int = 5,
) -> list[NormalizedContentEvent]:
    root = ET.fromstring(xml_text)
    events: list[NormalizedContentEvent] = []
    for entry in root.findall("atom:entry", ATOM_NS)[:limit]:
        video_id = entry.findtext("yt:videoId", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        href = link_el.get("href") if link_el is not None else f"https://youtu.be/{video_id}"
        if not video_id:
            continue
        published_at = None
        if published:
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                published_at = datetime.now(timezone.utc)
        events.append(
            NormalizedContentEvent(
                platform=PlatformType.YOUTUBE,
                event_type=ContentEventType.VIDEO_PUBLISHED,
                external_content_id=video_id,
                creator_platform_id=creator.platform_creator_id,
                creator_name=creator.display_name,
                creator_avatar=creator.avatar_url,
                title=title,
                content_url=href,
                playable_url=href,
                thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                published_at=published_at,
                raw_metadata={"source": "atom"},
            )
        )
    return events


def parse_websub_atom(xml_text: str) -> list[PlatformRawEvent]:
    root = ET.fromstring(xml_text)
    events: list[PlatformRawEvent] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=ATOM_NS)
        channel_id = entry.findtext("yt:channelId", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        href = link_el.get("href") if link_el is not None else None
        if not video_id or not channel_id:
            continue
        events.append(
            PlatformRawEvent(
                platform=PlatformType.YOUTUBE,
                event_type=ContentEventType.VIDEO_PUBLISHED,
                external_content_id=video_id,
                platform_creator_id=channel_id,
                raw={
                    "title": title,
                    "published": published,
                    "content_url": href,
                },
                received_at=datetime.now(timezone.utc),
            )
        )
    return events
