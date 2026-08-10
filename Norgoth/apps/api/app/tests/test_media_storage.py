"""Media storage keys, normalize, and factory defaults."""

from __future__ import annotations

import pytest

from app.services.media.factory import get_media_storage, reset_media_storage_cache
from app.services.media.keys import build_media_key
from app.services.media.local import LocalMediaStorage
from app.services.media.s3 import S3ConfigError, S3MediaStorage
from app.services.media.service import normalize_feed_media_url
from app.services.uploads.image_store import UploadValidationError, validate_image_bytes


def test_build_media_key_shape() -> None:
    key = build_media_key("123456789012345678", "png")
    assert key.startswith("guilds/123456789012345678/media/")
    assert key.endswith(".png")
    parts = key.split("/")
    assert len(parts) == 6


def test_build_media_key_rejects_bad_guild() -> None:
    with pytest.raises(ValueError):
        build_media_key("../evil", "png")


def test_normalize_feed_media_url() -> None:
    assert (
        normalize_feed_media_url(
            "https://cdn.discordapp.com/attachments/1/2/a.png"
        )
        is not None
    )
    rewritten = normalize_feed_media_url(
        "https://media.discordapp.net/attachments/1/2/a.png?ex=1"
    )
    assert rewritten is not None
    assert rewritten.startswith("https://cdn.discordapp.com/attachments/1/2/a.png")
    assert normalize_feed_media_url("not-a-url") is None
    assert normalize_feed_media_url("") is None
    assert normalize_feed_media_url(None) is None


def test_factory_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_media_storage_cache()

    class FakeSettings:
        media_storage_backend = "local"
        upload_dir = "var/uploads"
        aws_region = None
        aws_access_key_id = None
        aws_secret_access_key = None
        aws_s3_bucket_name = None
        aws_s3_endpoint_url = None
        aws_s3_public_base_url = None

    monkeypatch.setattr(
        "app.services.media.factory.get_settings", lambda: FakeSettings()
    )
    reset_media_storage_cache()
    storage = get_media_storage()
    assert isinstance(storage, LocalMediaStorage)
    reset_media_storage_cache()


def test_s3_requires_config() -> None:
    with pytest.raises(S3ConfigError):
        S3MediaStorage(
            bucket="",
            region="",
            access_key_id="",
            secret_access_key="",
        )


def test_validate_image_rejects_garbage() -> None:
    with pytest.raises(UploadValidationError):
        validate_image_bytes(b"not-an-image")
