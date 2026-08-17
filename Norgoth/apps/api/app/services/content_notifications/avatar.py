"""HTTPS-only creator avatar URL normalization and stale refresh."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.content_platforms.registry import get_adapter
from app.integrations.content_platforms.types import (
    PlatformAdapterError,
    PlatformBlockedError,
    PlatformType,
    ResolvedCreator,
)
from app.models.content_notifications import ContentCreatorSource
from app.services.content_notifications.rate_limit import throttle

logger = logging.getLogger("norgoth.content.avatar")

MAX_AVATAR_URL_LENGTH = 1024
MAX_WEBHOOK_AVATAR_URL_LENGTH = 500
AVATAR_REFRESH_TTL_SECONDS = 86400
AVATAR_STALE_AFTER = timedelta(days=7)
AVATAR_REFRESH_PER_REQUEST = 3
AVATAR_LOCK_PREFIX = "norgoth:cn:avatar-refresh:"
RESOLVE_CACHE_PREFIX = "norgoth:cn:resolve:"
RESOLVE_CACHE_TTL_SECONDS = 120
FUNCTIONAL_PLATFORMS = frozenset({"youtube", "twitch", "kick", "x"})
AVATAR_ALLOWED_HOSTS: dict[str, frozenset[str]] = {
    "youtube": frozenset({"yt3.ggpht.com", "yt3.googleusercontent.com"}),
    "twitch": frozenset({"static-cdn.jtvnw.net"}),
    "kick": frozenset({"files.kick.com"}),
    "x": frozenset({"pbs.twimg.com"}),
}


def normalize_https_avatar_url(url: str | None) -> str | None:
    """Return a https avatar URL, or None when the value is unsafe/unusable."""

    if not url or not isinstance(url, str):
        return None
    trimmed = url.strip()
    if not trimmed:
        return None
    lowered = trimmed.lower()
    if lowered.startswith("javascript:") or lowered.startswith("data:"):
        return None
    parsed = urlparse(trimmed)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host == "localhost":
        return None
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return None
    except ValueError:
        pass
    path = parsed.path
    if "pbs.twimg.com" in host and path.endswith("_normal.jpg"):
        path = path[: -len("_normal.jpg")] + "_200x200.jpg"
        trimmed = trimmed.replace(parsed.path, path, 1)
    elif "pbs.twimg.com" in host and path.endswith("_normal.png"):
        path = path[: -len("_normal.png")] + "_200x200.png"
        trimmed = trimmed.replace(parsed.path, path, 1)
    if len(trimmed) > MAX_AVATAR_URL_LENGTH:
        return None
    return trimmed


def persistable_source_avatar(platform: str, url: str | None) -> str | None:
    """HTTPS profile avatars only; Kick stream thumbnails are not stored on the source."""

    normalized = normalize_https_avatar_url(url)
    if not normalized:
        return None
    if platform == "kick" and "thumbnail" in normalized.lower():
        return None
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = AVATAR_ALLOWED_HOSTS.get(platform)
    if not allowed or host not in allowed:
        return None
    return normalized


def persistable_webhook_avatar(url: str | None) -> str | None:
    """HTTPS webhook identity avatars; any public host, no CN platform allowlist."""

    if url is None or not isinstance(url, str):
        return None
    trimmed = url.strip()
    if not trimmed:
        return None
    normalized = normalize_https_avatar_url(trimmed)
    if not normalized:
        return None
    if len(normalized) > MAX_WEBHOOK_AVATAR_URL_LENGTH:
        return None
    return normalized


def resolve_cache_key(guild_id: str, platform: str, url: str) -> str:
    digest = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
    return f"{RESOLVE_CACHE_PREFIX}{guild_id}:{platform}:{digest}"


def creator_cache_payload(creator: ResolvedCreator) -> dict[str, Any]:
    platform = creator.platform.value
    return {
        "platform": platform,
        "platform_creator_id": creator.platform_creator_id,
        "username": creator.username,
        "display_name": creator.display_name,
        "profile_url": creator.profile_url,
        "avatar_url": persistable_source_avatar(platform, creator.avatar_url),
        "canonical_url": creator.canonical_url,
        "metadata": creator.metadata,
    }


def creator_from_cache_payload(payload: dict[str, Any]) -> ResolvedCreator:
    return ResolvedCreator(
        platform=PlatformType(str(payload["platform"])),
        platform_creator_id=str(payload["platform_creator_id"]),
        username=str(payload.get("username") or ""),
        display_name=str(payload.get("display_name") or ""),
        profile_url=str(payload.get("profile_url") or ""),
        avatar_url=payload.get("avatar_url"),
        canonical_url=payload.get("canonical_url"),
        metadata=payload.get("metadata") or {},
    )


async def read_resolve_cache(
    guild_id: str, platform: str, url: str
) -> ResolvedCreator | None:
    from app.services.content_notifications.queue import get_redis

    redis_client = None
    try:
        redis_client = await get_redis()
        raw = await redis_client.get(resolve_cache_key(guild_id, platform, url))
        if not raw:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not payload.get("platform_creator_id"):
            return None
        return creator_from_cache_payload(payload)
    except Exception:  # noqa: BLE001
        return None
    finally:
        if redis_client is not None:
            await redis_client.aclose()


async def write_resolve_cache(
    guild_id: str, platform: str, url: str, creator: ResolvedCreator
) -> None:
    from app.services.content_notifications.queue import get_redis

    redis_client = None
    try:
        redis_client = await get_redis()
        await redis_client.set(
            resolve_cache_key(guild_id, platform, url),
            json.dumps(creator_cache_payload(creator)),
            ex=RESOLVE_CACHE_TTL_SECONDS,
        )
    except Exception:  # noqa: BLE001
        return
    finally:
        if redis_client is not None:
            await redis_client.aclose()


def source_needs_avatar_refresh(
    source: ContentCreatorSource,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    if not source.avatar_url:
        return True
    checked = source.avatar_checked_at
    if checked is None:
        return True
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    return current - checked >= AVATAR_STALE_AFTER


async def refresh_stale_avatars(
    session: AsyncSession,
    sources: Iterable[ContentCreatorSource],
) -> None:
    """Best-effort profile refresh for a page of sources. Never raises to callers."""

    candidates = [
        source
        for source in sources
        if source.platform in FUNCTIONAL_PLATFORMS
        and source_needs_avatar_refresh(source)
    ][:AVATAR_REFRESH_PER_REQUEST]
    if not candidates:
        return

    from app.services.content_notifications.queue import get_redis

    redis_client = None
    try:
        redis_client = await get_redis()
        for source in candidates:
            await _refresh_one(session, source, redis_client)
    except Exception:  # noqa: BLE001
        logger.warning("Avatar refresh skipped; redis or provider unavailable.")
    finally:
        if redis_client is not None:
            await redis_client.aclose()


async def _refresh_one(
    session: AsyncSession,
    source: ContentCreatorSource,
    redis_client: object,
) -> None:
    lock_key = f"{AVATAR_LOCK_PREFIX}{source.id}"
    try:
        acquired = await redis_client.set(  # type: ignore[union-attr]
            lock_key, "1", nx=True, ex=AVATAR_REFRESH_TTL_SECONDS
        )
    except Exception:  # noqa: BLE001
        return
    if not acquired:
        return
    if source.platform not in FUNCTIONAL_PLATFORMS:
        return
    if source.platform == "x":
        from app.services.content_notifications.x_budget import budget_exhausted

        try:
            if await budget_exhausted(redis_client):  # type: ignore[arg-type]
                return
        except Exception:  # noqa: BLE001
            return
    adapter = get_adapter(source.platform)
    if not adapter.is_available():
        return
    lookup = source.canonical_url or source.profile_url
    if not lookup:
        return
    try:
        await throttle(source.platform)
        creator = await adapter.resolve_account(lookup)
    except (PlatformBlockedError, PlatformAdapterError):
        source.avatar_checked_at = datetime.now(timezone.utc)
        return
    except Exception:  # noqa: BLE001
        logger.warning("Avatar resolve failed for source %s", source.id)
        source.avatar_checked_at = datetime.now(timezone.utc)
        return
    from app.services.content_notifications.fanout import ensure_source

    await ensure_source(
        session,
        platform=creator.platform.value,
        platform_creator_id=creator.platform_creator_id,
        username=creator.username,
        display_name=creator.display_name,
        profile_url=creator.profile_url,
        avatar_url=creator.avatar_url,
        canonical_url=creator.canonical_url,
        metadata=creator.metadata,
        monitor_status=source.monitor_status,
    )


def parse_account_platform_filter(platform: str | None) -> str | None:
    """Return a functional platform filter, or None for all. Raises ValueError."""

    if platform is None or platform.strip() == "" or platform.strip() == "all":
        return None
    normalized = platform.strip().lower()
    if normalized == "tiktok" or normalized not in FUNCTIONAL_PLATFORMS:
        raise ValueError(normalized)
    return normalized
