"""Factory for the configured MediaStorage provider."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.media.local import LocalMediaStorage
from app.services.media.protocol import MediaStorage
from app.services.media.s3 import S3ConfigError, S3MediaStorage


@lru_cache(maxsize=1)
def get_media_storage() -> MediaStorage:
    settings = get_settings()
    backend = (settings.media_storage_backend or "local").strip().lower()
    if backend == "local":
        return LocalMediaStorage(settings.upload_dir)
    if backend == "s3":
        return S3MediaStorage(
            bucket=settings.aws_s3_bucket_name or "",
            region=settings.aws_region or "",
            access_key_id=settings.aws_access_key_id or "",
            secret_access_key=settings.aws_secret_access_key or "",
            endpoint_url=settings.aws_s3_endpoint_url,
            public_base_url=settings.aws_s3_public_base_url,
        )
    raise S3ConfigError(
        f"Unsupported NORGOTH_MEDIA_STORAGE_BACKEND={backend!r}; use local or s3."
    )


def reset_media_storage_cache() -> None:
    get_media_storage.cache_clear()
