"""TikTok adapter — compliant boundary only (arbitrary monitoring blocked)."""

from __future__ import annotations

from app.integrations.content_platforms.base import ContentPlatformAdapter
from app.integrations.content_platforms.types import (
    NormalizedContentEvent,
    PlatformBlockedError,
    PlatformRawEvent,
    PlatformType,
    ResolvedCreator,
)


class TikTokAdapter(ContentPlatformAdapter):
    platform = PlatformType.TIKTOK

    def supports_push(self) -> bool:
        return False

    def is_available(self) -> bool:
        return False

    def availability_reason(self) -> str | None:
        return (
            "TikTok does not provide an approved API for monitoring arbitrary "
            "creator uploads. Display API and Content Posting webhooks require "
            "creator Login Kit OAuth for that user's content only and are not "
            "enabled for NorBot Content Notifications."
        )

    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        raise PlatformBlockedError(self.availability_reason() or "TikTok blocked")

    async def fetch_latest(
        self,
        creator: ResolvedCreator,
        *,
        limit: int = 5,
    ) -> list[NormalizedContentEvent]:
        raise PlatformBlockedError(self.availability_reason() or "TikTok blocked")

    async def enrich_event(self, event: PlatformRawEvent) -> NormalizedContentEvent:
        raise PlatformBlockedError(self.availability_reason() or "TikTok blocked")
