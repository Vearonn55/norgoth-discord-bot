"""RSS 2.0 / Atom parser and item identity helpers (clean-room)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urlparse, urlunparse
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"
MAX_ENTRIES = 50

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class FeedItem:
    item_key: str
    title: str
    link: str | None
    published: datetime | None
    summary_text: str
    author: str | None
    raw_id: str | None = None


@dataclass(frozen=True)
class ParsedFeed:
    format_hint: str  # rss20 | atom
    title: str | None
    items: list[FeedItem]


class FeedParseError(ValueError):
    """Raised when body is not a usable RSS 2.0 or Atom document."""


def html_to_text(value: str | None, *, max_len: int = 2000) -> str:
    if not value:
        return ""
    text = unescape(_TAG_RE.sub(" ", value))
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child_text(parent: Element, names: set[str]) -> str | None:
    for child in list(parent):
        if _local(child.tag) in names:
            if child.text and child.text.strip():
                return child.text.strip()
            # Atom XHTML / HTML content may nest.
            joined = "".join(child.itertext()).strip()
            return joined or None
    return None


def _atom_link(entry: Element) -> str | None:
    alternate: str | None = None
    first: str | None = None
    for child in list(entry):
        if _local(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if not href:
            continue
        if first is None:
            first = href
        rel = (child.attrib.get("rel") or "alternate").lower()
        if rel == "alternate":
            alternate = href
            break
    return alternate or first


def _rss_link(item: Element) -> str | None:
    for child in list(item):
        if _local(child.tag) == "link" and child.text and child.text.strip():
            return child.text.strip()
    # Some feeds put permalink in guid when isPermaLink=true
    for child in list(item):
        if _local(child.tag) == "guid":
            permalink = (child.attrib.get("isPermaLink") or "true").lower()
            text = (child.text or "").strip()
            if text and permalink != "false":
                return text
    return None


def canonicalize_link(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return url.strip()
    host = parsed.hostname or ""
    host = host.lower()
    netloc = host
    if parsed.port and parsed.port not in {80, 443}:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))


def compute_item_key(
    *,
    raw_id: str | None,
    link: str | None,
    title: str,
    published: datetime | None,
    summary_text: str,
) -> str:
    if raw_id and raw_id.strip():
        return f"id:{raw_id.strip()}"
    canonical = canonicalize_link(link)
    if canonical:
        return f"link:{canonical}"
    pub = published.isoformat() if published else ""
    digest = hashlib.sha256(
        f"{title}|{pub}|{summary_text[:200]}".encode("utf-8", errors="ignore")
    ).hexdigest()[:32]
    return f"hash:{digest}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    try:
        # Atom often ISO-8601
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError, IndexError):
        return None


def _build_item(
    *,
    raw_id: str | None,
    title: str | None,
    link: str | None,
    published: datetime | None,
    summary: str | None,
    author: str | None,
) -> FeedItem:
    title_text = html_to_text(title or "(untitled)", max_len=256) or "(untitled)"
    summary_text = html_to_text(summary, max_len=2000)
    key = compute_item_key(
        raw_id=raw_id,
        link=link,
        title=title_text,
        published=published,
        summary_text=summary_text,
    )
    return FeedItem(
        item_key=key,
        title=title_text,
        link=canonicalize_link(link) or link,
        published=published,
        summary_text=summary_text,
        author=html_to_text(author, max_len=128) or None,
        raw_id=raw_id,
    )


def _parse_rss(root: Element) -> ParsedFeed:
    channel = None
    for child in list(root):
        if _local(child.tag) == "channel":
            channel = child
            break
    if channel is None:
        raise FeedParseError("RSS document missing channel.")

    feed_title = _child_text(channel, {"title"})
    items: list[FeedItem] = []
    for child in list(channel):
        if _local(child.tag) != "item":
            continue
        guid = _child_text(child, {"guid"})
        title = _child_text(child, {"title"})
        link = _rss_link(child)
        published = _parse_datetime(_child_text(child, {"pubDate", "published"}))
        summary = _child_text(child, {"description", "summary", "content"})
        author = _child_text(child, {"author", "creator"})
        items.append(
            _build_item(
                raw_id=guid,
                title=title,
                link=link,
                published=published,
                summary=summary,
                author=author,
            )
        )
        if len(items) >= MAX_ENTRIES:
            break
    return ParsedFeed(format_hint="rss20", title=html_to_text(feed_title, max_len=256) or None, items=items)


def _parse_atom(root: Element) -> ParsedFeed:
    feed_title = _child_text(root, {"title"})
    items: list[FeedItem] = []
    for child in list(root):
        if _local(child.tag) != "entry":
            continue
        raw_id = _child_text(child, {"id"})
        title = _child_text(child, {"title"})
        link = _atom_link(child)
        published = _parse_datetime(
            _child_text(child, {"published"}) or _child_text(child, {"updated"})
        )
        summary = _child_text(child, {"summary", "content"})
        author = None
        for nested in list(child):
            if _local(nested.tag) == "author":
                author = _child_text(nested, {"name"})
                break
        items.append(
            _build_item(
                raw_id=raw_id,
                title=title,
                link=link,
                published=published,
                summary=summary,
                author=author,
            )
        )
        if len(items) >= MAX_ENTRIES:
            break
    return ParsedFeed(format_hint="atom", title=html_to_text(feed_title, max_len=256) or None, items=items)


def parse_feed(body: bytes | str) -> ParsedFeed:
    """Parse RSS 2.0 or Atom XML into a neutral item list."""

    if isinstance(body, bytes):
        text = body.decode("utf-8", errors="replace")
    else:
        text = body
    text = text.lstrip("\ufeff").strip()
    if not text:
        raise FeedParseError("Feed body is empty.")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise FeedParseError(f"Invalid XML: {exc}") from exc

    local = _local(root.tag).lower()
    if local == "rss":
        return _parse_rss(root)
    if local == "feed":
        return _parse_atom(root)
    raise FeedParseError("Document is not RSS 2.0 or Atom.")
