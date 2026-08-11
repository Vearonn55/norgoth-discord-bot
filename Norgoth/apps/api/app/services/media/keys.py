"""Collision-resistant object key helpers for media storage."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

_SAFE_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
_GUILD_ID_RE = re.compile(r"^[0-9]{5,25}$")


def build_media_key(guild_id: str, extension: str) -> str:
    """Return ``guilds/{guild_id}/media/{yyyy}/{mm}/{uuid}.{ext}``."""

    if not _GUILD_ID_RE.match(guild_id):
        raise ValueError("Invalid guild id for media key.")
    ext = (extension or "").lower().lstrip(".")
    if not _SAFE_EXT_RE.match(ext):
        raise ValueError("Invalid media file extension.")
    now = datetime.now(timezone.utc)
    return (
        f"guilds/{guild_id}/media/"
        f"{now.year:04d}/{now.month:02d}/"
        f"{uuid.uuid4().hex}.{ext}"
    )
