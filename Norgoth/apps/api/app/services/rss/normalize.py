"""Canonical RSS feed URL normalization for dedupe and persistence."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from app.security.ssrf import SsrfError, normalize_http_url


def _strip_trailing_slash(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, "")
    )


def canonical_feed_url(url: str) -> str:
    """Return a stable feed URL for storage and hashing.

    Syntax and private-literal checks run here. DNS / destination SSRF is
    enforced at fetch time so hashing does not depend on live resolution.
    """

    raw = (url or "").strip()
    if not raw:
        raise SsrfError("URL is required.", code="invalid_url")
    return _strip_trailing_slash(normalize_http_url(raw))
