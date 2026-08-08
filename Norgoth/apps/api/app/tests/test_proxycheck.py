"""Tests for the proxycheck.io integration."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.integrations.proxycheck import (
    InvalidProxycheckIPAddressError,
    ProxycheckClient,
    ProxycheckError,
)

API_KEY = "proxycheck-api-key"
IPV4_ADDRESS = "203.0.113.25"
IPV6_ADDRESS = "2001:db8::1"


def _build_response(payload: object) -> MagicMock:
    """Create a successful HTTP response mock."""

    response = MagicMock(spec=httpx.Response)
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    return response


@pytest.mark.anyio
async def test_check_ip_returns_clean_result() -> None:
    """A normal address should return a negative detection."""

    response = _build_response(
        {
            "status": "ok",
            "ip": IPV4_ADDRESS,
            IPV4_ADDRESS: {
                "detections": {
                    "anonymous": False,
                },
            },
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    result = await client.check_ip(IPV4_ADDRESS)

    assert result.ip_address == IPV4_ADDRESS
    assert result.anonymous is False
    assert result.vpn_or_proxy_detected is False
    assert result.status == "ok"

    http_client.get.assert_awaited_once_with(
        f"https://proxycheck.io/v3/{IPV4_ADDRESS}",
        params={
            "p": "0",
            "tag": "0",
            "ver": "24-June-2026",
            "key": API_KEY,
        },
    )
    response.raise_for_status.assert_called_once_with()


@pytest.mark.anyio
async def test_check_ip_returns_anonymous_detection() -> None:
    """An anonymous address should be marked as VPN or proxy."""

    response = _build_response(
        {
            "status": "ok",
            "ip": IPV4_ADDRESS,
            IPV4_ADDRESS: {
                "detections": {
                    "anonymous": True,
                },
            },
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    result = await client.check_ip(IPV4_ADDRESS)

    assert result.anonymous is True
    assert result.vpn_or_proxy_detected is True


@pytest.mark.anyio
async def test_check_ip_accepts_warning_response() -> None:
    """A successful lookup with a warning should remain usable."""

    response = _build_response(
        {
            "status": "warning",
            "message": "Approaching daily query limit.",
            "ip": IPV4_ADDRESS,
            IPV4_ADDRESS: {
                "detections": {
                    "anonymous": False,
                },
            },
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    result = await client.check_ip(IPV4_ADDRESS)

    assert result.status == "warning"
    assert result.vpn_or_proxy_detected is False


@pytest.mark.anyio
async def test_check_ip_can_run_without_api_key() -> None:
    """The client should support the limited keyless API mode."""

    response = _build_response(
        {
            "status": "ok",
            "ip": IPV4_ADDRESS,
            IPV4_ADDRESS: {
                "detections": {
                    "anonymous": False,
                },
            },
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
    )

    await client.check_ip(IPV4_ADDRESS)

    http_client.get.assert_awaited_once_with(
        f"https://proxycheck.io/v3/{IPV4_ADDRESS}",
        params={
            "p": "0",
            "tag": "0",
            "ver": "24-June-2026",
        },
    )


@pytest.mark.anyio
async def test_check_ip_normalizes_ipv6_address() -> None:
    """IPv6 addresses should be normalized and URL encoded."""

    expanded_address = "2001:0db8:0000:0000:0000:0000:0000:0001"
    encoded_address = "2001%3Adb8%3A%3A1"

    response = _build_response(
        {
            "status": "ok",
            "ip": IPV6_ADDRESS,
            IPV6_ADDRESS: {
                "detections": {
                    "anonymous": False,
                },
            },
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    result = await client.check_ip(expanded_address)

    assert result.ip_address == IPV6_ADDRESS

    http_client.get.assert_awaited_once_with(
        f"https://proxycheck.io/v3/{encoded_address}",
        params={
            "p": "0",
            "tag": "0",
            "ver": "24-June-2026",
            "key": API_KEY,
        },
    )


@pytest.mark.anyio
async def test_check_ip_wraps_http_error() -> None:
    """HTTP failures should use a stable integration error."""

    request = httpx.Request(
        "GET",
        f"https://proxycheck.io/v3/{IPV4_ADDRESS}",
    )
    response = httpx.Response(
        429,
        request=request,
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.side_effect = httpx.HTTPStatusError(
        "Too Many Requests",
        request=request,
        response=response,
    )

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    with pytest.raises(
        ProxycheckError,
        match="lookup failed",
    ):
        await client.check_ip(IPV4_ADDRESS)


@pytest.mark.anyio
async def test_check_ip_rejects_denied_status() -> None:
    """Denied API responses should not be treated as clean IPs."""

    response = _build_response(
        {
            "status": "denied",
            "message": "Daily query allowance exhausted.",
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    with pytest.raises(
        ProxycheckError,
        match="Daily query allowance exhausted",
    ):
        await client.check_ip(IPV4_ADDRESS)


@pytest.mark.anyio
async def test_check_ip_rejects_missing_detections() -> None:
    """Missing detection data should not default to a clean result."""

    response = _build_response(
        {
            "status": "ok",
            "ip": IPV4_ADDRESS,
            IPV4_ADDRESS: {},
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    with pytest.raises(
        ProxycheckError,
        match="detections payload",
    ):
        await client.check_ip(IPV4_ADDRESS)


@pytest.mark.anyio
async def test_check_ip_rejects_invalid_anonymous_value() -> None:
    """Non-boolean anonymous results should be rejected."""

    response = _build_response(
        {
            "status": "ok",
            "ip": IPV4_ADDRESS,
            IPV4_ADDRESS: {
                "detections": {
                    "anonymous": "yes",
                },
            },
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    with pytest.raises(
        ProxycheckError,
        match="anonymous result",
    ):
        await client.check_ip(IPV4_ADDRESS)


@pytest.mark.parametrize(
    "ip_address",
    [
        "",
        "not-an-ip",
        "999.999.999.999",
        "2001:db8:::1",
    ],
)
@pytest.mark.anyio
async def test_check_ip_rejects_invalid_address(
    ip_address: str,
) -> None:
    """Malformed IP addresses should be rejected before API access."""

    http_client = AsyncMock(spec=httpx.AsyncClient)

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    with pytest.raises(
        InvalidProxycheckIPAddressError,
        match="valid IPv4 or IPv6",
    ):
        await client.check_ip(ip_address)

    http_client.get.assert_not_awaited()


@pytest.mark.anyio
async def test_check_ip_rejects_invalid_json() -> None:
    """Malformed JSON should be converted to a stable error."""

    response = MagicMock(spec=httpx.Response)
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("Invalid JSON")

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = ProxycheckClient(
        http_client=http_client,
        api_key=API_KEY,
    )

    with pytest.raises(
        ProxycheckError,
        match="invalid JSON",
    ):
        await client.check_ip(IPV4_ADDRESS)
