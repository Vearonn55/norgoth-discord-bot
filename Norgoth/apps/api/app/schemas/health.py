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
