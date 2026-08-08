"""Registry of content platform adapters."""

from __future__ import annotations

from functools import lru_cache

from app.integrations.content_platforms.base import ContentPlatformAdapter
from app.integrations.content_platforms.kick.adapter import KickAdapter
from app.integrations.content_platforms.tiktok.adapter import TikTokAdapter
from app.integrations.content_platforms.twitch.adapter import TwitchAdapter
from app.integrations.content_platforms.types import PlatformAdapterError, PlatformType
from app.integrations.content_platforms.x.adapter import XAdapter
from app.integrations.content_platforms.youtube.adapter import YouTubeAdapter


@lru_cache(maxsize=1)
def get_adapters() -> dict[PlatformType, ContentPlatformAdapter]:
    return {
        PlatformType.YOUTUBE: YouTubeAdapter(),
        PlatformType.TWITCH: TwitchAdapter(),
        PlatformType.KICK: KickAdapter(),
        PlatformType.X: XAdapter(),
        PlatformType.TIKTOK: TikTokAdapter(),
    }


def get_adapter(platform: PlatformType | str) -> ContentPlatformAdapter:
    key = PlatformType(platform) if isinstance(platform, str) else platform
    adapters = get_adapters()
    adapter = adapters.get(key)
    if adapter is None:
        raise PlatformAdapterError(f"Unknown platform: {platform}")
    return adapter


def platform_availability() -> list[dict[str, object]]:
    rows = []
    for platform, adapter in get_adapters().items():
        rows.append(
            {
                "platform": platform.value,
                "available": adapter.is_available(),
                "supports_push": adapter.supports_push(),
                "reason": adapter.availability_reason(),
            }
        )
    return rows
