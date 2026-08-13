"""RSS / Atom parser unit tests."""

from __future__ import annotations

from app.services.rss.parser import compute_item_key, html_to_text, parse_feed

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Hello &lt;b&gt;World&lt;/b&gt;</title>
      <link>https://example.com/posts/1?utm=1</link>
      <guid>urn:example:1</guid>
      <description><![CDATA[<p>First <script>x</script> post</p>]]></description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second</title>
      <link>https://example.com/posts/2</link>
      <description>No guid</description>
    </item>
  </channel>
</rss>
"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <id>tag:example.org,2024:entry-1</id>
    <title>Atom One</title>
    <link href="https://example.com/a/1" rel="alternate"/>
    <updated>2024-02-01T10:00:00Z</updated>
    <summary>Hello atom</summary>
  </entry>
</feed>
"""


def test_parse_rss20() -> None:
    parsed = parse_feed(RSS_SAMPLE)
    assert parsed.format_hint == "rss20"
    assert parsed.title == "Example Feed"
    assert len(parsed.items) == 2
    assert parsed.items[0].item_key == "id:urn:example:1"
    assert "script" not in parsed.items[0].summary_text.lower()
    assert "First" in parsed.items[0].summary_text


def test_parse_atom() -> None:
    parsed = parse_feed(ATOM_SAMPLE)
    assert parsed.format_hint == "atom"
    assert parsed.items[0].item_key == "id:tag:example.org,2024:entry-1"
    assert parsed.items[0].link == "https://example.com/a/1"


def test_html_to_text_strips_tags() -> None:
    assert html_to_text("<b>Hi</b> there") == "Hi there"


def test_item_key_fallback_link_then_hash() -> None:
    assert compute_item_key(
        raw_id=None,
        link="https://Example.com/x",
        title="T",
        published=None,
        summary_text="",
    ).startswith("link:")
    key = compute_item_key(
        raw_id=None,
        link=None,
        title="Only title",
        published=None,
        summary_text="body",
    )
    assert key.startswith("hash:")
