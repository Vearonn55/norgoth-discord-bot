"""Amazon S3 (or S3-compatible) MediaStorage provider."""

from __future__ import annotations

import logging
from typing import Any

from app.services.media.cn_preview_keys import is_cn_preview_key
from app.services.media.keys import build_media_key
from app.services.media.protocol import StoredMedia
from app.services.uploads.image_store import validate_image_bytes

logger = logging.getLogger("norgoth.media.s3")


class S3ConfigError(RuntimeError):
    """Raised when S3 backend is selected without required configuration."""


class S3MediaStorage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        if not bucket or not region or not access_key_id or not secret_access_key:
            raise S3ConfigError(
                "S3 media backend requires AWS_S3_BUCKET_NAME, AWS_REGION, "
                "AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY."
            )
        self._bucket = bucket
        self._region = region
        self._public_base_url = (public_base_url or "").rstrip("/") or None
        self._endpoint_url = endpoint_url or None

        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as error:
            raise S3ConfigError(
                "boto3 is required when NORGOTH_MEDIA_STORAGE_BACKEND=s3."
            ) from error

        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": region,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
        }
        if self._endpoint_url:
            client_kwargs["endpoint_url"] = self._endpoint_url
        self._client = boto3.client(**client_kwargs)

    def build_key(self, guild_id: str, extension: str) -> str:
        return build_media_key(guild_id, extension)

    def upload(
        self,
        *,
        data: bytes,
        guild_id: str,
        extension: str,
        mime_type: str,
        public_base_url: str | None = None,
    ) -> StoredMedia:
        verified_ext, verified_mime, width, height = validate_image_bytes(data)
        extension = verified_ext
        mime_type = verified_mime
        key = self.build_key(guild_id, extension)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=mime_type,
        )
        logger.info(
            "S3 media upload success bucket=%s key=%s bytes=%s",
            self._bucket,
            key,
            len(data),
        )
        return StoredMedia(
            storage_key=key,
            public_url=self.public_url(key, public_base_url=public_base_url),
            mime_type=mime_type,
            byte_size=len(data),
            width=width,
            height=height,
            filename=key.rsplit("/", 1)[-1],
        )

    def upload_at_key(
        self,
        *,
        data: bytes,
        storage_key: str,
        mime_type: str,
        public_base_url: str | None = None,
    ) -> StoredMedia:
        verified_ext, verified_mime, width, height = validate_image_bytes(data)
        mime_type = verified_mime
        key = storage_key.strip()
        if not is_cn_preview_key(key):
            raise S3ConfigError("Invalid CN preview storage key.")
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=mime_type,
        )
        return StoredMedia(
            storage_key=key,
            public_url=self.public_url(key, public_base_url=public_base_url),
            mime_type=mime_type,
            byte_size=len(data),
            width=width,
            height=height,
            filename=key.rsplit("/", 1)[-1],
        )

    def delete(self, storage_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=storage_key)

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=storage_key)
            return True
        except Exception:  # noqa: BLE001
            return False

    def public_url(self, storage_key: str, *, public_base_url: str | None = None) -> str:
        base = (public_base_url or self._public_base_url or "").rstrip("/")
        if base:
            return f"{base}/{storage_key}"
        if self._endpoint_url:
            return f"{self._endpoint_url.rstrip('/')}/{self._bucket}/{storage_key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{storage_key}"
