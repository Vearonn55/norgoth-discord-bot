"""Trusted client IP extraction for verification and rate limiting."""

from __future__ import annotations

import ipaddress

from fastapi import Request

from app.core.config import Settings, get_settings

_LOOPBACK = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)


def _parse_ip(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _is_trusted_peer(host: str | None) -> bool:
    parsed = _parse_ip(host)
    if parsed is None:
        return False
    return any(parsed in network for network in _LOOPBACK)


def get_trusted_client_ip(request: Request, settings: Settings | None = None) -> str:
    """Return the client IP, trusting proxy headers only from loopback peers.

    Direct callers (including attackers hitting the API on loopback-published
    ports) cannot spoof X-Forwarded-For unless the peer itself is loopback,
    which is the nginx hop in production.
    """

    _ = settings or get_settings()
    peer = request.client.host if request.client else None
    if _is_trusted_peer(peer):
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            candidate = real_ip.split(",")[0].strip()
            if _parse_ip(candidate) is not None:
                return candidate
        forwarded = (request.headers.get("x-forwarded-for") or "").strip()
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            if _parse_ip(candidate) is not None:
                return candidate

    if peer:
        return peer
    raise ValueError("client_ip_unavailable")
