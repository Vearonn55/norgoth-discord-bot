"""RSS parser edge-case tests."""

from __future__ import annotations

from app.services.rss.parser import (
    MAX_ITEM_KEY_LEN,
    bound_item_key,
    compute_item_key,
    parse_feed,
)

GOOGLE_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>AI</title>
    <item>
      <title>One</title>
      <guid>https://example.com/1</guid>
      <description>Plain</description>
    </item>
    <item>
      <title>Two</title>
      <guid>urn:two</guid>
      <content:encoded><![CDATA[<p>Rich body</p>]]></content:encoded>
    </item>
  </channel>
</rss>
"""


def test_parse_google_style_fixture() -> None:
    parsed = parse_feed(GOOGLE_FIXTURE.encode("utf-8"), content_type="application/xml; charset=utf-8")
    assert parsed.format_hint == "rss20"
    assert parsed.title == "AI"
    assert len(parsed.items) == 2
    assert parsed.items[0].summary_text == "Plain"
    assert "Rich body" in parsed.items[1].summary_text


def test_parse_iso8859_encoding() -> None:
    body = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        '<rss version="2.0"><channel><title>café</title>'
        '<item><title>x</title><guid>1</guid></item></channel></rss>'
    ).encode("latin-1")
    parsed = parse_feed(body)
    assert parsed.title == "café"


def test_bound_item_key_hashes_long_guids() -> None:
    long_guid = "x" * 600
    key = compute_item_key(
        raw_id=long_guid,
        link=None,
        title="T",
        published=None,
        summary_text="",
    )
    assert len(key) <= MAX_ITEM_KEY_LEN
    assert key.startswith("id:")
    assert key == bound_item_key(f"id:{long_guid}")


def test_bound_item_key_preserves_short_keys() -> None:
    short = "id:abc123"
    assert bound_item_key(short) == short
