"""Platform adapter contract for content notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.integrations.content_platforms.types import (
    NormalizedContentEvent,
    PlatformRawEvent,
    PlatformType,
    ResolvedCreator,
)


class ContentPlatformAdapter(ABC):
    """Isolate platform-specific logic behind a common contract."""

    platform: PlatformType

    @abstractmethod
    async def resolve_account(self, input_url: str) -> ResolvedCreator:
        """Parse a creator URL/handle into a durable platform identity."""

    async def subscribe(self, creator: ResolvedCreator) -> dict[str, Any] | None:
        """Create an upstream push subscription when supported."""

        return None

    async def unsubscribe(self, creator: ResolvedCreator) -> None:
        """Remove an upstream push subscription when supported."""

        return None

    async def fetch_latest(
        self,
        creator: ResolvedCreator,
        *,
        limit: int = 5,
    ) -> list[NormalizedContentEvent]:
        """Return recent content for test/force notification flows."""

        return []

    async def enrich_event(
        self,
        event: PlatformRawEvent,
    ) -> NormalizedContentEvent:
        """Normalize a raw platform event into the shared event model."""

        raise NotImplementedError

    def supports_push(self) -> bool:
        return False

    def is_available(self) -> bool:
        """Return False when credentials or compliance block the platform."""

        return True

    def availability_reason(self) -> str | None:
        return None
