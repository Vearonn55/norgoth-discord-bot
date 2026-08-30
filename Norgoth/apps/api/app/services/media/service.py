"""Central media validation and Feed URL normalization."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse

from app.core.config import get_settings
from app.services.media.factory import get_media_storage
from app.services.media.protocol import MediaStorage, StoredMedia
from app.services.uploads.image_store import (
    ALLOWED_MIME_TYPES,
    UploadValidationError,
    validate_image_bytes,
)

logger = logging.getLogger("norgoth.media")

_DISCORD_CDN_HOSTS = frozenset(
    {
        "cdn.discordapp.com",
        "media.discordapp.net",
        "images-ext-1.discordapp.net",
        "images-ext-2.discordapp.net",
    }
)
_HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def normalize_feed_media_url(url: str | None) -> str | None:
    """Validate a Top Trending embed image URL without downloading.

    Allows Discord CDN and other https image URLs; returns None if unusable.
    Rewrites media.discordapp.net → cdn.discordapp.com for more reliable embeds.
    """

    if not url:
        return None
    cleaned = str(url).strip()[:1024]
    if not cleaned or not _HTTP_URL_RE.match(cleaned):
        return None
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    # Embed image field renders more reliably from cdn than media proxy host.
    if host == "media.discordapp.net":
        cleaned = urlunparse(parsed._replace(netloc="cdn.discordapp.com"))
    # Known Discord CDN hosts are preferred but any https URL is allowed
    # (Tenor/Giphy direct media, etc.).
    _ = _DISCORD_CDN_HOSTS
    return cleaned[:1024]


class MediaService:
    """Validate uploads and persist via the active MediaStorage provider."""

    def __init__(self, storage: MediaStorage | None = None) -> None:
        self._storage = storage

    @property
    def storage(self) -> MediaStorage:
        if self._storage is None:
            self._storage = get_media_storage()
        return self._storage

    def upload_image(
        self,
        *,
        data: bytes,
        guild_id: str,
        public_base_url: str | None = None,
        claimed_content_type: str | None = None,
    ) -> StoredMedia:
        settings = get_settings()
        if claimed_content_type and claimed_content_type not in ALLOWED_MIME_TYPES:
            raise UploadValidationError(
                "Unsupported media type. Allowed: PNG, JPEG, GIF, WEBP."
            )
        if len(data) > settings.max_upload_bytes:
            raise UploadValidationError(
                f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."
            )
        extension, mime_type, width, height = validate_image_bytes(data)
        logger.info(
            "Media upload provider=%s guild=%s mime=%s bytes=%s",
            getattr(settings, "media_storage_backend", "local"),
            guild_id,
            mime_type,
            len(data),
        )
        stored = self.storage.upload(
            data=data,
            guild_id=guild_id,
            extension=extension,
            mime_type=mime_type,
            public_base_url=public_base_url,
        )
        # Ensure dimensions from validation if provider omitted them.
        if stored.width is None:
            stored.width = width
        if stored.height is None:
            stored.height = height
        return stored

    def upload_cn_preview(
        self,
        *,
        data: bytes,
        platform: str,
        session_id: str,
        public_base_url: str | None = None,
    ) -> StoredMedia:
        from app.services.media.cn_preview_keys import build_cn_preview_key

        extension, mime_type, width, height = validate_image_bytes(data)
        settings = get_settings()
        if len(data) > settings.max_upload_bytes:
            raise UploadValidationError(
                f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."
            )
        key = build_cn_preview_key(platform, session_id, extension)
        upload_at_key = getattr(self.storage, "upload_at_key", None)
        if not callable(upload_at_key):
            raise UploadValidationError("Media storage does not support CN previews.")
        stored = upload_at_key(
            data=data,
            storage_key=key,
            mime_type=mime_type,
            public_base_url=public_base_url,
        )
        if stored.width is None:
            stored.width = width
        if stored.height is None:
            stored.height = height
        return stored
