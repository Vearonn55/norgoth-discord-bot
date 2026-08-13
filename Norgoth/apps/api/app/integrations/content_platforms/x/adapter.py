"""X / Twitter adapter with poll transport (stream pluggable later)."""

from __future__ import annotations

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

logger = logging.getLogger("norgoth.content.x")

X_API = "https://api.x.com/2"


class XAdapter(ContentPlatformAdapter):
    platform = PlatformType.X

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client

    def supports_push(self) -> bool:
        # Filtered stream webhook is Enterprise; default is poll.
        return False

    def is_available(self) -> bool:
        return bool(self._bearer())

    def availability_reason(self) -> str | None:
        if self.is_available():
            return None
        return "X_API_BEARER_TOKEN is required for post monitoring."

    def _bearer(self) -> str:
        return (
            os.getenv("X_API_BEARER_TOKEN", "").strip()
            or os.getenv("TWITTER_BEARER_TOKEN", "").strip()
        )

    def _client(self) -> httpx.AsyncClient:
        return self._http or httpx.AsyncClient(timeout=20.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer()}"}

    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        if not self.is_available():
            raise PlatformAdapterError(self.availability_reason() or "X unavailable")

        from app.services.content_notifications.x_budget import (
            budget_exhausted,
            record_reads,
        )

        if await budget_exhausted():
            raise PlatformAdapterError(
                "X monthly read budget exhausted.",
                code="quota_exhausted",
            )

        username = self._extract_username(input_url)
        owns = self._http is None
        client = self._client()
        try:
            response = await client.get(
                f"{X_API}/users/by/username/{username}",
                params={"user.fields": "profile_image_url,name,username"},
                headers=self._headers(),
            )
            await record_reads(1)
            if response.status_code == 429:
                raise PlatformAdapterError(
                    "X rate limited.",
                    code="rate_limited",
                )
            if response.status_code != 200:
                raise PlatformAdapterError(
                    f"X user lookup failed: HTTP {response.status_code}",
                    code="resolve_failed",
                )
            user = response.json().get("data") or {}
            user_id = str(user.get("id") or "")
            if not user_id:
                raise PlatformAdapterError("X user not found.", code="not_found")
            handle = user.get("username") or username
            return ResolvedCreator(
                platform=PlatformType.X,
                platform_creator_id=user_id,
                username=handle,
                display_name=user.get("name") or handle,
                profile_url=f"https://x.com/{handle}",
                avatar_url=user.get("profile_image_url"),
                canonical_url=f"https://x.com/{handle}",
            )
        finally:
            if owns:
                await client.aclose()

    def _extract_username(self, value: str) -> str:
        cleaned = value.strip().lstrip("@")
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        host = (parsed.hostname or "").lower()
        if host in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}:
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return parts[0]
        return cleaned.split("/")[0]

    async def fetch_latest(
        self,
        creator: ResolvedCreator,
        *,
        limit: int = 5,
    ) -> list[NormalizedContentEvent]:
        if not self.is_available():
            return []

        from app.services.content_notifications.x_budget import (
            budget_exhausted,
            record_reads,
        )

        if await budget_exhausted():
            logger.warning("X poll skipped: monthly read budget exhausted")
            return []

        owns = self._http is None
        client = self._client()
        try:
            response = await client.get(
                f"{X_API}/users/{creator.platform_creator_id}/tweets",
                params={
                    "max_results": max(5, min(limit, 100)),
                    "tweet.fields": "created_at,text,attachments",
                    "exclude": "replies,retweets",
                },
                headers=self._headers(),
            )
            await record_reads(1)
            if response.status_code == 429:
                logger.warning("X timeline fetch rate limited")
                return []
            if response.status_code != 200:
                logger.warning(
                    "X timeline fetch failed: %s %s",
                    response.status_code,
                    response.text,
                )
                return []
            data = response.json().get("data") or []
            events: list[NormalizedContentEvent] = []
            for post in data[:limit]:
                post_id = str(post.get("id"))
                url = f"https://x.com/{creator.username}/status/{post_id}"
                created = post.get("created_at")
                published_at = None
                if created:
                    try:
                        published_at = datetime.fromisoformat(
                            created.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_at = datetime.now(timezone.utc)
                events.append(
                    NormalizedContentEvent(
                        platform=PlatformType.X,
                        event_type=ContentEventType.POST_PUBLISHED,
                        external_content_id=post_id,
                        creator_platform_id=creator.platform_creator_id,
                        creator_name=creator.display_name,
                        creator_avatar=creator.avatar_url,
                        title=(post.get("text") or "")[:200],
                        description=post.get("text"),
                        content_url=url,
                        playable_url=url,
                        published_at=published_at,
                        raw_metadata=post,
                    )
                )
            return events
        finally:
            if owns:
                await client.aclose()

    async def enrich_event(self, event: PlatformRawEvent) -> NormalizedContentEvent:
        raw = event.raw
        username = raw.get("username") or ""
        post_id = event.external_content_id
        url = (
            f"https://x.com/{username}/status/{post_id}"
            if username
            else f"https://x.com/i/web/status/{post_id}"
        )
        return NormalizedContentEvent(
            platform=PlatformType.X,
            event_type=ContentEventType.POST_PUBLISHED,
            external_content_id=post_id,
            creator_platform_id=event.platform_creator_id,
            creator_name=str(raw.get("name") or username or event.platform_creator_id),
            creator_avatar=raw.get("avatar_url"),
            title=(raw.get("text") or "")[:200],
            description=raw.get("text"),
            content_url=url,
            playable_url=url,
            published_at=datetime.now(timezone.utc),
            raw_metadata=raw,
        )
