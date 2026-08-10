"""MediaStorage protocol for local and cloud object storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class StoredMedia:
    """Result of a successful media upload."""

    storage_key: str
    public_url: str
    mime_type: str
    byte_size: int
    width: int | None = None
    height: int | None = None
    filename: str | None = None


class MediaStorage(Protocol):
    """Provider-agnostic object storage operations."""

    def build_key(self, guild_id: str, extension: str) -> str:
        """Return a collision-resistant object key for this guild."""

    def upload(
        self,
        *,
        data: bytes,
        guild_id: str,
        extension: str,
        mime_type: str,
        public_base_url: str | None = None,
    ) -> StoredMedia:
        ...

    def delete(self, storage_key: str) -> None:
        ...

    def exists(self, storage_key: str) -> bool:
        ...

    def public_url(self, storage_key: str, *, public_base_url: str | None = None) -> str:
        ...
