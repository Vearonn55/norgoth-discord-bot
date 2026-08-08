"""Shared types for the multi-platform content notification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class PlatformType(StrEnum):
    YOUTUBE = "youtube"
    TWITCH = "twitch"
    KICK = "kick"
    X = "x"
    TIKTOK = "tiktok"


class ContentEventType(StrEnum):
    VIDEO_PUBLISHED = "VIDEO_PUBLISHED"
    STREAM_STARTED = "STREAM_STARTED"
    STREAM_ENDED = "STREAM_ENDED"
    POST_PUBLISHED = "POST_PUBLISHED"


class MonitorStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    AUTH_ERROR = "auth_error"
    SUBSCRIPTION_ERROR = "subscription_error"
    BLOCKED = "blocked"


class TransportType(StrEnum):
    WEBSUB = "websub"
    EVENTSUB = "eventsub"
    KICK_EVENTS = "kick_events"
    X_STREAM = "x_stream"
    POLL = "poll"


class SubscriptionOpStatus(StrEnum):
    ACTIVE = "active"
    WAITING_FIRST_EVENT = "waiting_first_event"
    SUBSCRIPTION_HEALTHY = "subscription_healthy"
    POLLING = "polling"
    PLATFORM_AUTH_ERROR = "platform_auth_error"
    DISCORD_PERMISSION_MISSING = "discord_permission_missing"
    WEBHOOK_MISSING = "webhook_missing"
    DESTINATION_CHANNEL_DELETED = "destination_channel_deleted"
    PAUSED = "paused"
    BLOCKED = "blocked"


class WebhookHealth(StrEnum):
    HEALTHY = "healthy"
    MISSING = "missing"
    INVALID = "invalid"
    PERMISSION_ERROR = "permission_error"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


@dataclass(slots=True)
class ResolvedCreator:
    platform: PlatformType
    platform_creator_id: str
    username: str
    display_name: str
    profile_url: str
    avatar_url: str | None = None
    canonical_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlatformRawEvent:
    platform: PlatformType
    event_type: ContentEventType
    external_content_id: str
    platform_creator_id: str
    raw: dict[str, Any] = field(default_factory=dict)
    received_at: datetime | None = None


@dataclass(slots=True)
class NormalizedContentEvent:
    platform: PlatformType
    event_type: ContentEventType
    external_content_id: str
    creator_platform_id: str
    creator_name: str
    creator_avatar: str | None = None
    title: str | None = None
    description: str | None = None
    content_url: str | None = None
    playable_url: str | None = None
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    is_live: bool | None = None
    game: str | None = None
    category: str | None = None
    viewer_count: int | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    source_id: UUID | None = None
    event_id: UUID | None = None


class PlatformAdapterError(Exception):
    """Raised when a platform adapter cannot complete an operation."""

    def __init__(self, message: str, *, code: str = "adapter_error") -> None:
        super().__init__(message)
        self.code = code


class PlatformBlockedError(PlatformAdapterError):
    """Raised when a platform cannot be monitored compliantly."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="platform_blocked")
