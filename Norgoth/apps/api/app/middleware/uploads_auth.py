"""Require a valid operator session cookie to read uploaded media."""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import Settings
from app.security.session import COOKIE_NAME, SessionService


class UploadsAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._sessions = SessionService()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not request.url.path.startswith("/uploads/"):
            return await call_next(request)
        if not self._settings.auth_enforced:
            return await call_next(request)
        cookie = request.cookies.get(COOKIE_NAME)
        if not cookie:
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})
        session = await self._sessions.get_session(cookie)
        if session is None:
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})
        return await call_next(request)
