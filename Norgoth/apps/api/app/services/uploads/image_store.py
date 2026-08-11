"""Validate and persist uploaded embed images to local disk.

Security posture:
- Only decodable raster images of an allowlisted format are accepted.
- The claimed content-type is never trusted; the bytes are re-decoded with
  Pillow to confirm the real format, and the stored extension is derived from
  that verified format.
- Filenames are generated (``{uuid4}.{ext}``); the client filename is ignored.
- Files are written under a per-guild directory inside a configured root.
"""

from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Verified Pillow format -> (extension, canonical mime type).
_ALLOWED_FORMATS: dict[str, tuple[str, str]] = {
    "PNG": ("png", "image/png"),
    "JPEG": ("jpg", "image/jpeg"),
    "GIF": ("gif", "image/gif"),
    "WEBP": ("webp", "image/webp"),
}

ALLOWED_MIME_TYPES = frozenset(mime for _, mime in _ALLOWED_FORMATS.values())

_GUILD_ID_RE = re.compile(r"^[0-9]{5,25}$")

# apps/api directory (contains the ``app`` package): image_store.py is at
# app/services/uploads/image_store.py -> parents[3] == apps/api.
_API_ROOT = Path(__file__).resolve().parents[3]


def resolve_upload_root(upload_dir: str) -> Path:
    """Resolve a possibly-relative configured upload dir to an absolute path."""
    candidate = Path(upload_dir)
    if not candidate.is_absolute():
        candidate = _API_ROOT / candidate
    return candidate


class UploadValidationError(Exception):
    """Raised when an uploaded file fails validation."""


@dataclass(slots=True)
class StoredImage:
    filename: str
    stored_path: str
    public_url: str
    mime_type: str
    byte_size: int
    width: int
    height: int


def _safe_guild_id(guild_id: str) -> str:
    if not _GUILD_ID_RE.match(guild_id):
        raise UploadValidationError("Invalid guild id.")
    return guild_id


def validate_image_bytes(data: bytes) -> tuple[str, str, int, int]:
    """Return ``(extension, mime_type, width, height)`` for valid image bytes.

    Raises :class:`UploadValidationError` for anything that is not a decodable
    image in the allowlisted set.
    """
    if not data:
        raise UploadValidationError("Empty file.")

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            # verify() detects truncated/corrupt files.
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise UploadValidationError("File is not a valid image.") from error

    if image_format not in _ALLOWED_FORMATS:
        raise UploadValidationError(
            "Unsupported image format. Allowed: PNG, JPEG, GIF, WEBP."
        )

    extension, mime_type = _ALLOWED_FORMATS[image_format]
    return extension, mime_type, int(width), int(height)


def store_image(
    *,
    data: bytes,
    guild_id: str,
    upload_root: Path,
    public_base_url: str,
) -> StoredImage:
    """Validate and persist an image, returning its stored metadata."""
    guild = _safe_guild_id(guild_id)
    extension, mime_type, width, height = validate_image_bytes(data)

    filename = f"{uuid.uuid4().hex}.{extension}"
    guild_dir = (upload_root / guild).resolve()
    root_resolved = upload_root.resolve()
    # Defense in depth: ensure the target stays under the upload root.
    if root_resolved not in guild_dir.parents and guild_dir != root_resolved:
        raise UploadValidationError("Invalid storage path.")
    guild_dir.mkdir(parents=True, exist_ok=True)

    destination = guild_dir / filename
    destination.write_bytes(data)

    public_url = f"{public_base_url.rstrip('/')}/uploads/{guild}/{filename}"
    stored_path = str(destination)

    return StoredImage(
        filename=filename,
        stored_path=stored_path,
        public_url=public_url,
        mime_type=mime_type,
        byte_size=len(data),
        width=width,
        height=height,
    )


def delete_stored_file(stored_path: str, upload_root: Path) -> None:
    """Delete a stored file if it lives under the upload root."""
    try:
        target = Path(stored_path).resolve()
    except (OSError, ValueError):
        return
    root_resolved = upload_root.resolve()
    if root_resolved not in target.parents:
        return
    target.unlink(missing_ok=True)
