"""Preview/thumbnail URL helpers for content notification adapters."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.integrations.content_platforms.types import PlatformType

_TRUSTED_PREVIEW_SUFFIXES: dict[PlatformType, tuple[str, ...]] = {
    PlatformType.KICK: (
        "kick.com",
        "files.kick.com",
        "images.kick.com",
    ),
    PlatformType.TWITCH: (
        "jtvnw.net",
        "ttvnw.net",
    ),
    PlatformType.YOUTUBE: (
        "ytimg.com",
        "ggpht.com",
    ),
}


def _coerce_url(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, dict):
        nested = value.get("url") or value.get("src")
        if isinstance(nested, str):
            trimmed = nested.strip()
            return trimmed or None
    return None


def extract_stream_thumbnail(payload: dict[str, Any]) -> str | None:
    """Return a live/content preview URL from a Kick stream-like payload."""

    stream = payload.get("stream") if isinstance(payload.get("stream"), dict) else {}
    for candidate in (
        payload.get("thumbnail"),
        payload.get("thumbnail_url"),
        _coerce_url(payload.get("thumbnail")),
        stream.get("thumbnail"),
        stream.get("thumbnail_url"),
        _coerce_url(stream.get("thumbnail")),
    ):
        url = _coerce_url(candidate)
        if url:
            return url
    return None


def normalize_twitch_preview_url(url: str | None) -> str | None:
    if not url:
        return None
    return url.replace("{width}", "1280").replace("{height}", "720")


def is_trusted_preview_host(platform: PlatformType, url: str) -> bool:
    """Return True when the preview URL host is on the platform allowlist."""

    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    suffixes = _TRUSTED_PREVIEW_SUFFIXES.get(platform)
    if not suffixes:
        return True
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)


__all__ = [
    "extract_stream_thumbnail",
    "is_trusted_preview_host",
    "normalize_twitch_preview_url",
]
