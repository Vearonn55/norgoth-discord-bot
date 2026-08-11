"""Tests for uploaded image validation and safe storage."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from app.services.uploads.image_store import (
    UploadValidationError,
    resolve_upload_root,
    store_image,
    validate_image_bytes,
)


def _png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_validate_accepts_png() -> None:
    ext, mime, width, height = validate_image_bytes(_png_bytes((12, 8)))
    assert ext == "png"
    assert mime == "image/png"
    assert (width, height) == (12, 8)


def test_validate_rejects_non_image() -> None:
    with pytest.raises(UploadValidationError):
        validate_image_bytes(b"this is definitely not an image")


def test_validate_rejects_empty() -> None:
    with pytest.raises(UploadValidationError):
        validate_image_bytes(b"")


def test_store_image_writes_uuid_named_file(tmp_path: Path) -> None:
    stored = store_image(
        data=_png_bytes(),
        guild_id="123456789",
        upload_root=tmp_path,
        public_base_url="https://api.example.com/",
    )
    written = Path(stored.stored_path)
    assert written.exists()
    # Filename is a generated uuid, never the client's name.
    assert written.name == stored.filename
    assert written.suffix == ".png"
    assert stored.public_url == (
        f"https://api.example.com/uploads/123456789/{stored.filename}"
    )
    assert stored.mime_type == "image/png"
    assert stored.byte_size > 0


def test_store_image_rejects_bad_guild(tmp_path: Path) -> None:
    with pytest.raises(UploadValidationError):
        store_image(
            data=_png_bytes(),
            guild_id="../etc",
            upload_root=tmp_path,
            public_base_url="https://api.example.com",
        )


def test_resolve_upload_root_relative() -> None:
    root = resolve_upload_root("var/uploads")
    assert root.is_absolute()
    assert root.name == "uploads"
