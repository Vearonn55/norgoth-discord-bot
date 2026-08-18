"""Probe + bootstrap helpers for RSS feeds."""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rss_feeds import RssFeedConfig, RssFeedItem
from app.security.ssrf import SafeFetchResult, SsrfError, safe_fetch
from app.services.rss.parser import FeedParseError, ParsedFeed, parse_feed
from app.services.rss.normalize import canonical_feed_url
from app.services.rss.quotas import (
    MAX_ITEMS_RETAINED,
    clamp_poll_interval,
    feed_url_hash,
    next_poll_after_success,
)

logger = logging.getLogger("norgoth.rss.probe")

PROBE_ERROR_MESSAGES: dict[str, str] = {
    "invalid_url": "The feed URL is invalid or unsupported.",
    "unsafe_destination": "That destination is not allowed.",
    "not_found": "The feed was not found.",
    "access_denied": "The source denied access to this feed.",
    "rate_limited": "The source is rate limiting requests.",
    "remote_unavailable": "The remote server is unavailable.",
    "timeout": "The connection timed out.",
    "tls_failed": "TLS validation failed.",
    "too_large": "The feed response is too large.",
    "unsupported_content": "The response is not a supported feed type.",
    "invalid_document": "The document is not a valid RSS or Atom feed.",
}

MAX_DISPLAY_NAME_LEN = 200


@dataclass
class ProbeResult:
    ok: bool
    error: str | None
    format_hint: str | None
    feed_title: str | None
    sample_title: str | None
    item_count: int
    etag: str | None
    last_modified: str | None
    final_url: str | None
    parsed: ParsedFeed | None
    error_code: str | None = None


def _probe_fail(
    code: str,
    *,
    error: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    final_url: str | None = None,
) -> ProbeResult:
    return ProbeResult(
        ok=False,
        error=error or PROBE_ERROR_MESSAGES.get(code, "Feed probe failed."),
        error_code=code,
        format_hint=None,
        feed_title=None,
        sample_title=None,
        item_count=0,
        etag=etag,
        last_modified=last_modified,
        final_url=final_url,
        parsed=None,
    )


def _size_class(nbytes: int) -> str:
    if nbytes < 16 * 1024:
        return "lt_16kib"
    if nbytes < 64 * 1024:
        return "lt_64kib"
    if nbytes < 256 * 1024:
        return "lt_256kib"
    if nbytes < 1024 * 1024:
        return "lt_1mib"
    return "gte_1mib"


def classify_http_status(status_code: int) -> str:
    if status_code == 404:
        return "not_found"
    if status_code in {401, 403}:
        return "access_denied"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "remote_unavailable"
    if status_code >= 400:
        return "remote_unavailable"
    return "remote_unavailable"


def classify_transport_error(exc: BaseException) -> str:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.InvalidURL):
        return "invalid_url"
    if isinstance(exc, ssl.SSLError):
        return "tls_failed"
    cause = exc.__cause__ or getattr(exc, "__context__", None)
    if isinstance(cause, BaseException) and cause is not exc:
        if isinstance(cause, (ssl.SSLError, httpx.TimeoutException, TimeoutError)):
            return classify_transport_error(cause)
    text = str(exc).lower()
    if "certificate" in text or "ssl" in text or "tls" in text:
        return "tls_failed"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "remote_unavailable"


def _content_looks_like_feed(content_type: str | None) -> bool:
    if not content_type:
        return True
    lowered = content_type.lower()
    return any(
        token in lowered
        for token in ("xml", "rss", "atom", "text/plain", "octet-stream")
    )


def clamp_display_name(value: str | None, *, max_len: int = MAX_DISPLAY_NAME_LEN) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) <= max_len:
        return trimmed
    return trimmed[: max_len - 1].rstrip() + "…"


def _probe_from_fetch(
    result: SafeFetchResult,
) -> ProbeResult:
    if result.status_code >= 400:
        reason = classify_http_status(result.status_code)
        return _probe_fail(
            reason,
            etag=result.headers.get("etag"),
            last_modified=result.headers.get("last-modified"),
            final_url=result.final_url,
        )

    try:
        parsed = parse_feed(
            result.body,
            content_type=result.headers.get("content-type"),
        )
    except FeedParseError:
        content_type = result.headers.get("content-type")
        reason = (
            "unsupported_content"
            if not _content_looks_like_feed(content_type)
            else "invalid_document"
        )
        return _probe_fail(
            reason,
            etag=result.headers.get("etag"),
            last_modified=result.headers.get("last-modified"),
            final_url=result.final_url,
        )

    sample = parsed.items[0].title if parsed.items else None
    return ProbeResult(
        ok=True,
        error=None,
        error_code=None,
        format_hint=parsed.format_hint,
        feed_title=parsed.title,
        sample_title=sample,
        item_count=len(parsed.items),
        etag=result.headers.get("etag"),
        last_modified=result.headers.get("last-modified"),
        final_url=result.final_url,
        parsed=parsed,
    )


async def fetch_and_parse_feed(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> ProbeResult:
    """Shared hardened fetch + parse pipeline for probe and create."""

    try:
        canonical = canonical_feed_url(url)
    except SsrfError as exc:
        code = getattr(exc, "code", None) or "unsafe_destination"
        return _probe_fail(code)

    try:
        result = await safe_fetch(canonical, client=client)
    except SsrfError as exc:
        code = getattr(exc, "code", None) or "unsafe_destination"
        return _probe_fail(code)
    except (httpx.HTTPError, httpx.InvalidURL, ssl.SSLError) as exc:
        return _probe_fail(classify_transport_error(exc))
    except MemoryError:
        return _probe_fail("too_large")

    return _probe_from_fetch(result)


async def probe_feed_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> ProbeResult:
    started = time.monotonic()
    redirect_count = 0
    size_class = "none"
    parser = "none"
    reason = "ok"
    result_ok = False
    try:
        probe = await fetch_and_parse_feed(url, client=client)
        result_ok = probe.ok
        if probe.ok and probe.parsed is not None:
            parser = probe.format_hint or "unknown"
            reason = "ok"
        elif probe.error_code:
            reason = probe.error_code
        else:
            reason = "invalid_document"
        return probe
    finally:
        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "rss_probe ok=%s reason=%s latency_ms=%s redirects=%s size_class=%s parser=%s",
            result_ok,
            reason,
            latency_ms,
            redirect_count,
            size_class,
            parser,
        )


async def bootstrap_items(
    session: AsyncSession,
    feed: RssFeedConfig,
    parsed: ParsedFeed,
) -> int:
    """Mark current items as seen without publishing. Returns count inserted."""

    if not parsed.items:
        return 0

    now = datetime.now(timezone.utc)
    keys = [item.item_key for item in parsed.items]
    existing_keys = set(
        (
            await session.scalars(
                select(RssFeedItem.item_key).where(
                    RssFeedItem.feed_id == feed.id,
                    RssFeedItem.item_key.in_(keys),
                )
            )
        ).all()
    )

    inserted = 0
    for item in parsed.items:
        if item.item_key in existing_keys:
            continue
        session.add(
            RssFeedItem(
                feed_id=feed.id,
                item_key=item.item_key,
                published_at=item.published,
                first_seen_at=now,
                skipped_reason="bootstrap",
            )
        )
        existing_keys.add(item.item_key)
        inserted += 1
    await session.flush()
    return inserted


async def prune_old_items(session: AsyncSession, feed_id: UUID) -> None:
    """Keep the newest MAX_ITEMS_RETAINED rows per feed."""

    count = await session.scalar(
        select(func.count()).select_from(RssFeedItem).where(
            RssFeedItem.feed_id == feed_id
        )
    )
    if not count or count <= MAX_ITEMS_RETAINED:
        return

    # Delete oldest beyond retention.
    excess = int(count) - MAX_ITEMS_RETAINED
    oldest_ids = (
        await session.scalars(
            select(RssFeedItem.id)
            .where(RssFeedItem.feed_id == feed_id)
            .order_by(RssFeedItem.first_seen_at.asc())
            .limit(excess)
        )
    ).all()
    if oldest_ids:
        await session.execute(
            delete(RssFeedItem).where(RssFeedItem.id.in_(list(oldest_ids)))
        )


def serialize_feed(feed: RssFeedConfig) -> dict[str, Any]:
    return {
        "id": str(feed.id),
        "guild_id": feed.guild_id,
        "feed_url": feed.feed_url,
        "display_name": feed.display_name,
        "channel_id": feed.channel_id,
        "mention_role_id": feed.mention_role_id,
        "enabled": bool(feed.enabled),
        "poll_interval_seconds": int(feed.poll_interval_seconds),
        "format_hint": feed.format_hint,
        "next_poll_at": feed.next_poll_at.isoformat() if feed.next_poll_at else None,
        "last_success_at": (
            feed.last_success_at.isoformat() if feed.last_success_at else None
        ),
        "last_error": feed.last_error,
        "failure_count": int(feed.failure_count or 0),
        "created_at": feed.created_at.isoformat() if feed.created_at else None,
        "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
    }


# re-export for routes
__all__ = [
    "ProbeResult",
    "bootstrap_items",
    "clamp_display_name",
    "clamp_poll_interval",
    "feed_url_hash",
    "fetch_and_parse_feed",
    "next_poll_after_success",
    "probe_feed_url",
    "prune_old_items",
    "serialize_feed",
]
