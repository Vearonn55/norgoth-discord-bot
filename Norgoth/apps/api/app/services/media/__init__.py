"""Media storage abstraction (local disk + S3-ready)."""

from __future__ import annotations

from app.services.media.factory import get_media_storage
from app.services.media.service import MediaService, normalize_feed_media_url

__all__ = [
    "MediaService",
    "get_media_storage",
    "normalize_feed_media_url",
]
