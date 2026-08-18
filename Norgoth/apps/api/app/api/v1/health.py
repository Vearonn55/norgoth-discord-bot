"""Application health-check routes."""

import os

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Check API liveness",
)
async def get_health() -> HealthResponse:
    """Return the current API liveness state."""

    settings = get_settings()
    release_sha = os.getenv("NORGOTH_RELEASE_SHA", "").strip() or None

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        release_sha=release_sha,
        discord_client_id=settings.discord_client_id,
        discord_application_id=settings.discord_application_id,
        discord_identity_mismatch=(
            settings.discord_client_id is not None
            and settings.discord_application_id is not None
            and settings.discord_client_id != settings.discord_application_id
        ),
    )
