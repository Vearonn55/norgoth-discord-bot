"""Authenticated observability endpoints for Command Center operators."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.dependencies_auth import require_operator_session
from app.services.campaign_store import get_redis
from app.services.worker_registry import aggregate_workers_health

router = APIRouter(
    prefix="/observability",
    tags=["Observability"],
    dependencies=[Depends(require_operator_session)],
)


@router.get("/workers/health")
async def get_workers_health() -> dict[str, Any]:
    """Aggregate heartbeat status for every registered NorBot worker."""

    redis_client = await get_redis()
    try:
        return await aggregate_workers_health(redis_client)
    finally:
        await redis_client.aclose()
