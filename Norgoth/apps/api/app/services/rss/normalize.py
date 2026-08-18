"""Canonical RSS feed URL normalization for dedupe and persistence."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from app.security.ssrf import SsrfError, validate_url_for_fetch


def _strip_trailing_slash(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, "")
    )


def canonical_feed_url(url: str) -> str:
    """Return a stable, SSRF-validated feed URL for storage and hashing."""

    raw = (url or "").strip()
    if not raw:
        raise SsrfError("URL is required.", code="invalid_url")
    return _strip_trailing_slash(validate_url_for_fetch(raw))
