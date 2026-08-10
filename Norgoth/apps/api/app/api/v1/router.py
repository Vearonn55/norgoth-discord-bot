"""Version 1 API router composition."""

from fastapi import APIRouter

from app.api.v1.configuration import (
    router as configuration_router,
)
from app.api.v1.dashboard_oauth import router as dashboard_oauth_router
from app.api.v1.guilds import router as guilds_router
from app.api.v1.health import router as health_router
from app.api.v1.high_risk_guilds import (
    router as high_risk_guilds_router,
)
from app.api.v1.oauth import router as oauth_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.user_lists import router as user_lists_router
from app.api.v1.verification_logs import (
    router as verification_logs_router,
)

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(guilds_router)
api_router.include_router(configuration_router)
api_router.include_router(user_lists_router)
api_router.include_router(high_risk_guilds_router)
api_router.include_router(verification_logs_router)
api_router.include_router(oauth_router)
api_router.include_router(dashboard_oauth_router)
api_router.include_router(sessions_router)
