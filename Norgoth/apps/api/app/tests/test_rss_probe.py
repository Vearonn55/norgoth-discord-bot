"""RSS probe error mapping — mocked HTTP, no live network."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from defusedxml.common import EntitiesForbidden

from app.security.ssrf import SsrfError
from app.services.rss.parser import FeedParseError, parse_feed
from app.services.rss.service import ProbeResult, probe_feed_url
from app.tests.test_rss_parser import ATOM_SAMPLE, RSS_SAMPLE


def _fetch_result(
    *,
    body: bytes = b"",
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    final_url: str = "https://example.com/feed.xml",
    redirect_count: int = 0,
):
    result = MagicMock()
    result.body = body
    result.status_code = status_code
    result.headers = headers or {"content-type": "application/rss+xml"}
    result.final_url = final_url
    result.redirect_count = redirect_count
    return result


@pytest.mark.asyncio
async def test_probe_valid_rss_and_atom() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(body=RSS_SAMPLE.encode())),
    ):
        rss = await probe_feed_url("https://example.com/rss.xml")
    assert rss.ok is True
    assert rss.error_code is None
    assert rss.format_hint == "rss20"
    assert rss.feed_title == "Example Feed"
    assert rss.parsed is not None
    assert "<rss" not in (rss.feed_title or "")

    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(body=ATOM_SAMPLE.encode())),
    ):
        atom = await probe_feed_url("https://example.com/atom.xml")
    assert atom.ok is True
    assert atom.format_hint == "atom"


@pytest.mark.asyncio
async def test_probe_malformed_xml_is_invalid_document() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(body=b"<not-a-feed")),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == "invalid_document"


@pytest.mark.asyncio
async def test_probe_entities_forbidden_is_invalid_document() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(body=b"<rss/>")),
    ), patch(
        "app.services.rss.service.parse_feed",
        side_effect=FeedParseError("Invalid XML."),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == "invalid_document"


def test_parse_feed_wraps_entities_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_text: str):
        raise EntitiesForbidden("amp", "x", "", "", "", "")

    monkeypatch.setattr("app.services.rss.parser.ET.fromstring", boom)
    with pytest.raises(FeedParseError, match="Invalid XML"):
        parse_feed("<rss></rss>")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (SsrfError("Only http and https URLs are allowed.", code="invalid_url"), "invalid_url"),
        (SsrfError("URL resolves to a blocked address.", code="unsafe_destination"), "unsafe_destination"),
        (SsrfError("Response body exceeds size limit.", code="too_large"), "too_large"),
        (SsrfError("Too many redirects.", code="unsafe_destination"), "unsafe_destination"),
        (httpx.ConnectTimeout("timeout"), "timeout"),
        (httpx.ReadTimeout("timeout"), "timeout"),
        (httpx.ConnectError("boom"), "remote_unavailable"),
        (httpx.InvalidURL("bad"), "invalid_url"),
    ],
)
async def test_probe_maps_expected_fetch_failures(exc: Exception, code: str) -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(side_effect=exc),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == code
    assert result.error
    assert "<rss" not in result.error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (403, "access_denied"),
        (404, "not_found"),
        (429, "rate_limited"),
        (503, "remote_unavailable"),
    ],
)
async def test_probe_maps_http_status(status: int, code: str) -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(status_code=status, body=b"nope")),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == code


@pytest.mark.asyncio
async def test_probe_tls_failure() -> None:
    import ssl

    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(side_effect=ssl.SSLError("cert verify failed")),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == "tls_failed"


@pytest.mark.asyncio
async def test_probe_html_content_type_with_invalid_body() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(
            return_value=_fetch_result(
                body=b"<html>not a feed</html>",
                headers={"content-type": "text/html"},
            )
        ),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == "unsupported_content"


@pytest.mark.asyncio
async def test_probe_missing_content_type_with_valid_rss() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(
            return_value=_fetch_result(
                body=RSS_SAMPLE.encode(),
                headers={},
            )
        ),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is True
    assert result.format_hint == "rss20"


@pytest.mark.asyncio
async def test_probe_empty_feed_is_success() -> None:
    empty = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(body=empty)),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is True
    assert result.item_count == 0


@pytest.mark.asyncio
async def test_probe_does_not_map_cancellation_to_ok_false() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(side_effect=httpx.RequestError("cancelled")),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    assert result.ok is False
    assert result.error_code == "remote_unavailable"


@pytest.mark.asyncio
async def test_probe_success_payload_has_no_raw_xml() -> None:
    with patch(
        "app.services.rss.service.safe_fetch",
        new=AsyncMock(return_value=_fetch_result(body=RSS_SAMPLE.encode())),
    ):
        result = await probe_feed_url("https://example.com/feed.xml")
    dumped = repr(result.error) + repr(result.feed_title) + repr(result.sample_title)
    assert "<?xml" not in dumped
    assert "<item>" not in dumped
    assert isinstance(result, ProbeResult)
