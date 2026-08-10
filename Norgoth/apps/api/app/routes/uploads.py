"""Guild-scoped image upload endpoint for embed media."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Path, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_database_session
from app.models.embed_messages import EmbedMediaAsset
from app.services.media.factory import get_media_storage
from app.services.media.local import LocalMediaStorage
from app.services.media.service import MediaService
from app.services.uploads.image_store import UploadValidationError

logger = logging.getLogger("norgoth.uploads")

router = APIRouter(
    tags=["Uploads"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE = r"^[0-9]{5,25}$"


@router.post("/guilds/{guild_id}/uploads/image")
async def upload_image(
    request: Request,
    guild_id: str = Path(pattern=SNOWFLAKE),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, object]:
    settings = get_settings()
    max_bytes = settings.max_upload_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.",
        )

    public_base = settings.public_api_url or str(request.base_url).rstrip("/")
    service = MediaService(get_media_storage())

    try:
        stored = service.upload_image(
            data=data,
            guild_id=guild_id,
            public_base_url=public_base,
            claimed_content_type=file.content_type,
        )
    except UploadValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        logger.exception("Failed to store uploaded image")
        raise HTTPException(status_code=500, detail="Failed to store image.") from error
    except Exception as error:  # noqa: BLE001
        logger.exception("Media upload failed")
        raise HTTPException(status_code=500, detail=str(error)) from error

    # Local provider: keep absolute path for legacy delete helpers; else key.
    storage = get_media_storage()
    if isinstance(storage, LocalMediaStorage):
        from app.services.uploads.image_store import resolve_upload_root

        abs_path = str(
            (resolve_upload_root(settings.upload_dir) / stored.storage_key).resolve()
        )
    else:
        abs_path = stored.storage_key

    asset = EmbedMediaAsset(
        guild_id=guild_id,
        filename=stored.filename or stored.storage_key.rsplit("/", 1)[-1],
        stored_path=abs_path[:500],
        public_url=stored.public_url[:600],
        mime_type=stored.mime_type,
        byte_size=stored.byte_size,
        width=stored.width,
        height=stored.height,
        storage_provider=(settings.media_storage_backend or "local")[:32],
        storage_key=stored.storage_key[:512],
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)

    logger.info(
        "Media record created id=%s provider=%s key=%s",
        asset.id,
        asset.storage_provider,
        asset.storage_key,
    )

    return {
        "id": str(asset.id),
        "url": asset.public_url,
        "mime_type": asset.mime_type,
        "byte_size": asset.byte_size,
        "width": asset.width,
        "height": asset.height,
        "storage_provider": asset.storage_provider,
    }
