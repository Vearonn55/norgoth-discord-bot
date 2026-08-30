"""Local filesystem MediaStorage backed by existing upload helpers."""

from __future__ import annotations

from pathlib import Path

from app.services.media.cn_preview_keys import is_cn_preview_key
from app.services.media.keys import build_media_key
from app.services.media.protocol import StoredMedia
from app.services.uploads.image_store import (
    UploadValidationError,
    resolve_upload_root,
    validate_image_bytes,
)


class LocalMediaStorage:
    def __init__(self, upload_dir: str) -> None:
        self._upload_root = resolve_upload_root(upload_dir)

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
        # Re-validate bytes; extension/mime from caller must match.
        verified_ext, verified_mime, width, height = validate_image_bytes(data)
        if verified_ext != extension.lstrip(".") or verified_mime != mime_type:
            # Prefer verified format over caller claims.
            extension = verified_ext
            mime_type = verified_mime

        key = self.build_key(guild_id, extension)
        destination = (self._upload_root / key).resolve()
        root = self._upload_root.resolve()
        if root not in destination.parents and destination != root:
            raise UploadValidationError("Invalid storage path.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

        base = (public_base_url or "").rstrip("/")
        public = f"{base}/uploads/{key}" if base else f"/uploads/{key}"
        return StoredMedia(
            storage_key=key,
            public_url=public,
            mime_type=mime_type,
            byte_size=len(data),
            width=width,
            height=height,
            filename=Path(key).name,
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
            raise UploadValidationError("Invalid CN preview storage key.")
        destination = (self._upload_root / key).resolve()
        root = self._upload_root.resolve()
        if root not in destination.parents and destination != root:
            raise UploadValidationError("Invalid storage path.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        base = (public_base_url or "").rstrip("/")
        public = f"{base}/uploads/{key}" if base else f"/uploads/{key}"
        return StoredMedia(
            storage_key=key,
            public_url=public,
            mime_type=mime_type,
            byte_size=len(data),
            width=width,
            height=height,
            filename=Path(key).name,
        )

    def delete(self, storage_key: str) -> None:
        target = (self._upload_root / storage_key).resolve()
        root = self._upload_root.resolve()
        if root not in target.parents:
            return
        target.unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        target = (self._upload_root / storage_key).resolve()
        root = self._upload_root.resolve()
        if root not in target.parents:
            return False
        return target.is_file()

    def public_url(self, storage_key: str, *, public_base_url: str | None = None) -> str:
        base = (public_base_url or "").rstrip("/")
        return f"{base}/uploads/{storage_key}" if base else f"/uploads/{storage_key}"
