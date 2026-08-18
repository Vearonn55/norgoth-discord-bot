"""Unit tests for SSRF-safe URL validation and fetch policy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.security.ssrf import (
    SsrfError,
    resolve_and_validate_host,
    safe_fetch,
    validate_url_for_fetch,
    validate_url_syntax,
)


def test_reject_non_http_scheme() -> None:
    with pytest.raises(SsrfError, match="http and https"):
        validate_url_syntax("ftp://example.com/feed.xml")


def test_reject_userinfo() -> None:
    with pytest.raises(SsrfError, match="credentials"):
        validate_url_syntax("https://user:pass@example.com/feed.xml")


def test_reject_non_default_port() -> None:
    with pytest.raises(SsrfError, match="ports"):
        validate_url_syntax("https://example.com:8080/feed.xml")


def test_reject_literal_private_ip() -> None:
    with pytest.raises(SsrfError, match="blocked"):
        validate_url_syntax("http://127.0.0.1/feed.xml")
    with pytest.raises(SsrfError, match="blocked"):
        validate_url_syntax("http://10.0.0.5/feed.xml")
    with pytest.raises(SsrfError, match="blocked"):
        validate_url_syntax("http://169.254.169.254/latest/meta-data")
    with pytest.raises(SsrfError, match="blocked"):
        validate_url_syntax("http://[::ffff:127.0.0.1]/feed.xml")


def test_public_ipv6_literal_is_allowed() -> None:
    scheme, host, port, path = validate_url_syntax(
        "https://[2606:4700:10::6814:179a]/feed.xml"
    )
    assert scheme == "https"
    assert host == "2606:4700:10::6814:179a"
    assert path.startswith("/feed.xml")
    assert port is None


def test_reject_dns_to_private(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host, *args, **kwargs):  # noqa: ANN001
        return [
            (None, None, None, None, ("10.1.2.3", 0)),
        ]

    monkeypatch.setattr("app.security.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SsrfError, match="blocked"):
        resolve_and_validate_host("evil.example")


def test_validate_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host, *args, **kwargs):  # noqa: ANN001
        return [
            (None, None, None, None, ("93.184.216.34", 0)),
        ]

    monkeypatch.setattr("app.security.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    url = validate_url_for_fetch("https://example.com/feed.xml")
    assert url.startswith("https://example.com/")


@pytest.mark.asyncio
async def test_safe_fetch_oversized_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.security.ssrf.resolve_and_validate_host",
        lambda host: ["93.184.216.34"],
    )

    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/xml"}
    response.content = b"x" * (2 * 1024 * 1024 + 1)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=response)
    client.aclose = AsyncMock()

    with pytest.raises(SsrfError, match="size limit"):
        await safe_fetch("https://example.com/feed.xml", client=client)


@pytest.mark.asyncio
async def test_safe_fetch_streams_and_aborts_oversized_httpx_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.security.ssrf.resolve_and_validate_host",
        lambda host: ["93.184.216.34"],
    )

    payload = b"x" * (2 * 1024 * 1024 + 50)

    class _StreamResponse:
        status_code = 200
        headers = {"content-type": "application/xml"}

        async def aiter_bytes(self, chunk_size: int = 65536):
            for index in range(0, len(payload), chunk_size):
                yield payload[index : index + chunk_size]

        async def aclose(self) -> None:
            return None

    stream = _StreamResponse()

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=stream)
    client.aclose = AsyncMock()

    with pytest.raises(SsrfError, match="size limit") as exc:
        await safe_fetch("https://example.com/feed.xml", client=client)
    assert exc.value.code == "too_large"


@pytest.mark.asyncio
async def test_safe_fetch_redirect_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.security.ssrf.resolve_and_validate_host",
        lambda host: ["93.184.216.34"],
    )
    redirect = MagicMock()
    redirect.status_code = 302
    redirect.headers = {"location": "https://example.com/feed.xml"}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=redirect)
    client.aclose = AsyncMock()
    with pytest.raises(SsrfError, match="Too many redirects") as exc:
        await safe_fetch("https://example.com/feed.xml", client=client)
    assert exc.value.code == "unsafe_destination"

    pinned = client.request.await_args.args[1]
    assert pinned.startswith("https://93.184.216.34/")
    assert client.request.await_args.kwargs["headers"]["Host"] == "example.com"


@pytest.mark.asyncio
async def test_safe_fetch_pins_resolved_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.security.ssrf.resolve_and_validate_host",
        lambda host: ["93.184.216.34"],
    )

    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/xml"}
    response.content = b"<rss/>"

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=response)
    client.aclose = AsyncMock()

    result = await safe_fetch("https://example.com/feed.xml", client=client)
    assert result.status_code == 200
    assert client.request.await_args.args[1] == "https://93.184.216.34/feed.xml"


@pytest.mark.asyncio
async def test_safe_fetch_redirect_to_private(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_resolve(host: str) -> list[str]:
        calls["n"] += 1
        if host == "evil.internal":
            raise SsrfError("URL resolves to a blocked address.")
        return ["93.184.216.34"]

    monkeypatch.setattr("app.security.ssrf.resolve_and_validate_host", fake_resolve)

    redirect = MagicMock()
    redirect.status_code = 302
    redirect.headers = {"location": "http://evil.internal/secret"}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=redirect)
    client.aclose = AsyncMock()

    with pytest.raises(SsrfError, match="blocked"):
        await safe_fetch("https://example.com/feed.xml", client=client)
