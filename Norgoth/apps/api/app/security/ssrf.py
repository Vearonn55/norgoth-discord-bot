"""SSRF-safe URL validation and outbound HTTP fetch for user-supplied URLs."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MiB
MAX_REDIRECTS = 5
CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 15.0
ALLOWED_PORTS = {80, 443, None}


class SsrfError(Exception):
    """Raised when a URL or redirect target fails SSRF policy."""


@dataclass(frozen=True)
class SafeFetchResult:
    url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    final_url: str


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified:
        return True
    # IPv6 ULA fc00::/7
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv6_mapped is None:
        if int(ip) & (0xFE << 120) == (0xFC << 120):
            return True
    # Cloud metadata / common link-local
    if str(ip) in {"169.254.169.254", "169.254.170.2"}:
        return True
    return False


def validate_url_syntax(url: str) -> tuple[str, str, int | None, str]:
    """Return (scheme, hostname, port, path_query) or raise SsrfError."""

    raw = (url or "").strip()
    if not raw:
        raise SsrfError("URL is required.")
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise SsrfError("Only http and https URLs are allowed.")
    if parsed.username or parsed.password:
        raise SsrfError("URLs with embedded credentials are not allowed.")
    host = parsed.hostname
    if not host:
        raise SsrfError("URL host is required.")
    # Literal IP in hostname — validate immediately.
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        if _is_blocked_ip(ip):
            raise SsrfError("URL resolves to a blocked address.")
    except ValueError:
        pass  # hostname, not IP

    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    effective = port if port is not None else default_port
    if effective not in {80, 443}:
        raise SsrfError("Only ports 80 and 443 are allowed.")

    # Rebuild without fragment; keep path/query.
    path = parsed.path or "/"
    query = parsed.query or ""
    return scheme, host.lower(), port, path + (f"?{query}" if query else "")


def resolve_and_validate_host(hostname: str) -> list[str]:
    """Resolve hostname and ensure every address is publicly routable."""

    try:
        # Literal IP
        ip = ipaddress.ip_address(hostname.strip("[]"))
        if _is_blocked_ip(ip):
            raise SsrfError("URL resolves to a blocked address.")
        return [str(ip)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SsrfError(f"DNS resolution failed for host: {hostname}") from exc

    if not infos:
        raise SsrfError(f"DNS resolution returned no addresses for host: {hostname}")

    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise SsrfError(f"Invalid resolved address: {addr}") from exc
        if _is_blocked_ip(ip):
            raise SsrfError("URL resolves to a blocked address.")
        addresses.append(str(ip))
    return addresses


def validate_url_for_fetch(url: str) -> str:
    """Validate scheme/host/port and DNS; return normalized URL string."""

    scheme, host, port, path_query = validate_url_syntax(url)
    resolve_and_validate_host(host)
    netloc = host if port is None else f"{host}:{port}"
    # Prefer bracket form for IPv6 literals in URL.
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        if isinstance(ip, ipaddress.IPv6Address):
            netloc = f"[{host.strip('[]')}]" if port is None else f"[{host.strip('[]')}]:{port}"
    except ValueError:
        pass
    path, _, query = path_query.partition("?")
    return urlunparse((scheme, netloc, path or "/", "", query, ""))


def _url_with_ip(url: str, ip: str, port: int | None, scheme: str) -> str:
    parsed = urlparse(url)
    try:
        ip_obj = ipaddress.ip_address(ip)
        host = f"[{ip}]" if isinstance(ip_obj, ipaddress.IPv6Address) else ip
    except ValueError:
        host = ip
    netloc = host if port is None else f"{host}:{port}"
    if port is None:
        netloc = host
    return urlunparse((scheme, netloc, parsed.path or "/", "", parsed.query, ""))


async def _resolve_host_async(hostname: str) -> list[str]:
    return await asyncio.to_thread(resolve_and_validate_host, hostname)


async def safe_fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    max_body_bytes: int = MAX_BODY_BYTES,
    client: httpx.AsyncClient | None = None,
) -> SafeFetchResult:
    """Fetch ``url`` with SSRF checks, manual redirects, and body size cap."""

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
            follow_redirects=False,
            trust_env=False,
        )

    request_headers: dict[str, str] = {
        "User-Agent": "NorBot-RSS/1.0 (+https://norgoth.local)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    if headers:
        request_headers.update(headers)
    if etag:
        request_headers["If-None-Match"] = etag
    if last_modified:
        request_headers["If-Modified-Since"] = last_modified

    current = validate_url_for_fetch(url)
    await _resolve_host_async(urlparse(current).hostname or "")

    try:
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port, _pq = validate_url_syntax(current)
            resolved = await _resolve_host_async(host)
            pin_ip = resolved[0]
            request_headers["Host"] = host if port is None else f"{host}:{port}"
            pinned_url = _url_with_ip(current, pin_ip, port, scheme)

            response = await client.request(
                method,
                pinned_url,
                headers=request_headers,
                follow_redirects=False,
                extensions={"sni_hostname": host} if scheme == "https" else None,
            )

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise SsrfError("Redirect missing Location header.")
                next_url = urljoin(current, location)
                current = validate_url_for_fetch(next_url)
                # 303 / 302 historically switch to GET for browsers; keep method for 307/308.
                if response.status_code in {301, 302, 303}:
                    method = "GET"
                continue

            body = response.content
            if len(body) > max_body_bytes:
                raise SsrfError("Response body exceeds size limit.")

            header_map = {k.lower(): v for k, v in response.headers.items()}
            return SafeFetchResult(
                url=url,
                status_code=response.status_code,
                headers=header_map,
                body=body,
                final_url=current,
            )

        raise SsrfError("Too many redirects.")
    finally:
        if owns_client:
            await client.aclose()


# Back-compat alias used by services.
SafeHttpFetcher = Any  # marker for docs; callers use safe_fetch directly
