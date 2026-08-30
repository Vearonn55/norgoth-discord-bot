"""Canonical live-stream URL validation for Discord Link buttons."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlparse, urlunparse

from app.integrations.content_platforms.types import PlatformType

logger = logging.getLogger("norgoth.content.stream_urls")

_YOUTUBE_VIDEO_RE = re.compile(r"^[a-zA-Z0-9_-]{6,32}$")

_ALLOWED_HOSTS: dict[PlatformType, frozenset[str]] = {
    PlatformType.TWITCH: frozenset({"twitch.tv", "www.twitch.tv", "m.twitch.tv"}),
    PlatformType.KICK: frozenset({"kick.com", "www.kick.com"}),
    PlatformType.YOUTUBE: frozenset(
        {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
    ),
}


def _canonical_host(host: str) -> str:
    return host.lower().rstrip(".")


def validate_canonical_stream_url(
    platform: PlatformType,
    url: str | None,
    *,
    video_id: str | None = None,
) -> str | None:
    """Return a safe https stream URL for Link buttons, or None."""

    if not url or not isinstance(url, str):
        logger.info(
            "cn_stream_url_invalid platform=%s reason=missing",
            platform.value,
        )
        return None
    trimmed = url.strip()
    parsed = urlparse(trimmed)
    if parsed.scheme != "https" or not parsed.netloc:
        logger.info(
            "cn_stream_url_invalid platform=%s reason=scheme",
            platform.value,
        )
        return None
    if parsed.username or parsed.password:
        logger.info(
            "cn_stream_url_invalid platform=%s reason=credentials",
            platform.value,
        )
        return None
    host = _canonical_host(parsed.hostname or "")
    allowed = _ALLOWED_HOSTS.get(platform)
    if not allowed or host not in allowed:
        logger.info(
            "cn_stream_url_invalid platform=%s reason=host",
            platform.value,
        )
        return None

    if platform == PlatformType.TWITCH:
        parts = [segment for segment in parsed.path.split("/") if segment]
        login = parts[0] if parts else ""
        if not login:
            return None
        return f"https://www.twitch.tv/{login}"

    if platform == PlatformType.KICK:
        parts = [segment for segment in parsed.path.split("/") if segment]
        slug = parts[0] if parts else ""
        if not slug:
            return None
        return f"https://kick.com/{slug}"

    if platform == PlatformType.YOUTUBE:
        vid = video_id
        if host == "youtu.be":
            parts = [segment for segment in parsed.path.split("/") if segment]
            vid = vid or (parts[0] if parts else None)
        else:
            query = parse_qs(parsed.query or "")
            vid = vid or ((query.get("v") or [None])[0])
        if not vid or not _YOUTUBE_VIDEO_RE.match(vid):
            logger.info(
                "cn_stream_url_invalid platform=%s reason=video_id",
                platform.value,
            )
            return None
        return f"https://www.youtube.com/watch?v={vid}"

    return urlunparse(("https", host, parsed.path or "/", "", parsed.query, ""))
