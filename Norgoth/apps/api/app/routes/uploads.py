"""Guild-scoped image upload endpoint for embed media."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Path, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_database_session
from app.models.embed_messages import EmbedMediaAsset
from app.services.uploads.image_store import (
    ALLOWED_MIME_TYPES,
    UploadValidationError,
    resolve_upload_root,
    store_image,
)

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

    # Reject obviously-wrong content types early (bytes are re-verified later).
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type. Allowed: PNG, JPEG, GIF, WEBP.",
        )

    max_bytes = settings.max_upload_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.",
        )

    upload_root = resolve_upload_root(settings.upload_dir)
    public_base = settings.public_api_url or str(request.base_url).rstrip("/")

    try:
        stored = store_image(
            data=data,
            guild_id=guild_id,
            upload_root=upload_root,
            public_base_url=public_base,
        )
    except UploadValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        logger.exception("Failed to store uploaded image")
        raise HTTPException(status_code=500, detail="Failed to store image.") from error

    asset = EmbedMediaAsset(
        guild_id=guild_id,
        filename=stored.filename,
        stored_path=stored.stored_path,
        public_url=stored.public_url,
        mime_type=stored.mime_type,
        byte_size=stored.byte_size,
        width=stored.width,
        height=stored.height,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)

    return {
        "id": str(asset.id),
        "url": asset.public_url,
        "mime_type": asset.mime_type,
        "byte_size": asset.byte_size,
        "width": asset.width,
        "height": asset.height,
    }
