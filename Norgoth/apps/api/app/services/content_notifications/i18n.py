"""Localized strings for content notification delivery."""

from __future__ import annotations

from app.integrations.content_platforms.types import PlatformType

_SUPPORTED_LOCALES = frozenset({"en", "tr"})

_WATCH_LABELS: dict[tuple[str, PlatformType], str] = {
    ("en", PlatformType.TWITCH): "Watch on Twitch",
    ("tr", PlatformType.TWITCH): "Twitch'te İzle",
    ("en", PlatformType.KICK): "Watch on Kick",
    ("tr", PlatformType.KICK): "Kick'te İzle",
    ("en", PlatformType.YOUTUBE): "Watch on YouTube",
    ("tr", PlatformType.YOUTUBE): "YouTube'da İzle",
}


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return "en"
    primary = locale.strip().lower().split("-", 1)[0]
    return primary if primary in _SUPPORTED_LOCALES else "en"


def watch_on_platform_label(platform: PlatformType, *, locale: str | None = None) -> str:
    loc = normalize_locale(locale)
    return _WATCH_LABELS.get((loc, platform)) or _WATCH_LABELS.get(
        ("en", platform), f"Watch on {platform.value.title()}"
    )
