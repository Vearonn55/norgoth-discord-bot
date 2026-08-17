"""Pure Auto Moderation checks for image-only and link-only channels.

These helpers inspect Discord message metadata only. They never fetch user
URLs or treat Discord-generated embeds as proof of an image.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_TRAILING_PUNCT = ".,);]>\"'"
_SAFE_SCHEMES = {"http", "https"}
_FORWARD_TYPE_NAMES = {"forward"}


def _content_type_is_image(content_type: str | None) -> bool:
    if not content_type:
        return False
    return content_type.lower().split(";", 1)[0].strip().startswith("image/")


def message_has_image_attachment(message: Any) -> bool:
    """True when every attachment is ``image/*`` and at least one exists."""

    attachments = list(getattr(message, "attachments", None) or [])
    if not attachments:
        return False
    for attachment in attachments:
        if not _content_type_is_image(getattr(attachment, "content_type", None)):
            return False
    return True


def is_forwarded_message(message: Any) -> bool:
    snapshots = getattr(message, "message_snapshots", None)
    if snapshots:
        return True
    flags = getattr(message, "flags", None)
    if flags is not None and bool(getattr(flags, "is_forwarded", False)):
        return True
    msg_type = getattr(message, "type", None)
    name = getattr(msg_type, "name", "") or ""
    return name in _FORWARD_TYPE_NAMES


def is_image_only_compliant(message: Any, *, caption_allowed: bool = True) -> bool:
    """Return True when the message satisfies Image Only Channel policy."""

    if getattr(message, "poll", None) is not None:
        return False
    stickers = list(getattr(message, "stickers", None) or [])
    if stickers:
        return False
    if is_forwarded_message(message) and not message_has_image_attachment(message):
        return False
    if not message_has_image_attachment(message):
        return False
    if not caption_allowed:
        content = (getattr(message, "content", None) or "").strip()
        if content:
            return False
    return True


def _unwrap_autolink(token: str) -> str:
    if token.startswith("<") and token.endswith(">") and "://" in token[1:-1]:
        return token[1:-1]
    return token


def _strip_one_trailing_punct(token: str) -> str:
    if token and token[-1] in _TRAILING_PUNCT:
        return token[:-1]
    return token


def _is_complete_http_url(token: str) -> bool:
    try:
        parsed = urlparse(token)
    except ValueError:
        return False
    if parsed.scheme.lower() not in _SAFE_SCHEMES:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    host = parsed.hostname
    if not host:
        return False
    try:
        host.encode("idna")
    except (UnicodeError, ValueError):
        return False
    return True


def is_link_only_content(content: str) -> bool:
    """True when every whitespace-separated token is a complete http(s) URL."""

    text = (content or "").strip()
    if not text:
        return False
    tokens = text.split()
    if not tokens:
        return False
    for token in tokens:
        cleaned = _strip_one_trailing_punct(_unwrap_autolink(token))
        if not cleaned or not _is_complete_http_url(cleaned):
            return False
    return True


def is_link_only_compliant(message: Any) -> bool:
    """Return True when the message satisfies Link Only Channel policy."""

    if getattr(message, "poll", None) is not None:
        return False
    if list(getattr(message, "attachments", None) or []):
        return False
    if list(getattr(message, "stickers", None) or []):
        return False
    if is_forwarded_message(message):
        return False
    return is_link_only_content(getattr(message, "content", None) or "")
