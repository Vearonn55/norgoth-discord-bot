"""Origin allowlist for cookie-authenticated mutating requests."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import Settings
from app.security.cors_origins import cors_allow_origins
from app.security.session import COOKIE_NAME

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_PUBLIC_PREFIXES = (
    "/webhooks/",
    "/internal/",
    "/api/v1/oauth/",
    "/api/v1/sessions/exchange",
    "/api/v1/health",
    "/tickets/transcript/",
    "/bot/health",
    "/campaigns/worker/health",
)


def _origin_from_request(request: Request) -> str | None:
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if origin:
        return origin
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return None
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """Reject cross-site mutating cookie requests that lack an allowed Origin."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._allowed = set(cors_allow_origins(settings))

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method.upper() in _SAFE_METHODS:
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)
        if COOKIE_NAME not in request.cookies:
            return await call_next(request)

        origin = _origin_from_request(request)
        if origin is None or origin not in self._allowed:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin request rejected."},
            )
        return await call_next(request)
