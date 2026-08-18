"""Health-check response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response returned by the application liveness endpoint."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str
    version: str
    environment: str
    release_sha: str | None = None
    discord_client_id: str | None = None
    discord_application_id: str | None = None
    discord_identity_mismatch: bool | None = None
