"""Object keys for shared content-notification stream preview snapshots."""

from __future__ import annotations

import hashlib
import re
import uuid

_PLATFORM_RE = re.compile(r"^[a-z]{2,16}$")
_SAFE_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")


def build_cn_preview_key(platform: str, session_id: str, extension: str) -> str:
    """Return ``cn-previews/{platform}/{hash}/{uuid}.{ext}``."""

    plat = (platform or "").strip().lower()
    if not _PLATFORM_RE.match(plat):
        raise ValueError("Invalid platform for CN preview key.")
    ext = (extension or "").lower().lstrip(".")
    if not _SAFE_EXT_RE.match(ext):
        raise ValueError("Invalid media file extension.")
    digest = hashlib.sha256((session_id or "").encode("utf-8")).hexdigest()[:16]
    return f"cn-previews/{plat}/{digest}/{uuid.uuid4().hex}.{ext}"


def is_cn_preview_key(storage_key: str) -> bool:
    return (storage_key or "").startswith("cn-previews/")


__all__ = ["build_cn_preview_key", "is_cn_preview_key"]
