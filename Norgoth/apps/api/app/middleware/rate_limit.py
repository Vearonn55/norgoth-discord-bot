"""Coarse Redis rate limits for public and authenticated API routes."""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.security.client_ip import get_trusted_client_ip
from app.services.campaign_store import get_redis

_PUBLIC_LIMIT = 60
_AUTH_LIMIT = 240
_WINDOW_SECONDS = 60


def _bucket_for(path: str) -> tuple[str, int]:
    if path.startswith("/webhooks/") or "/oauth/" in path:
        return "public", _PUBLIC_LIMIT
    if path.startswith("/uploads") or path.endswith("/uploads/image"):
        return "upload", 30
    if path.startswith("/campaigns"):
        return "campaigns", 120
    return "api", _AUTH_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path
        if path in {"/api/v1/health", "/bot/health", "/campaigns/worker/health", "/"}:
            return await call_next(request)
        if get_settings().environment in {"testing", "test"}:
            return await call_next(request)

        try:
            identity = get_trusted_client_ip(request)
        except ValueError:
            identity = "unknown"
        bucket, limit = _bucket_for(path)
        key = f"norgoth:ratelimit:{bucket}:{identity}"
        redis_client = await get_redis()
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, _WINDOW_SECONDS)
            if int(count) > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded."},
                    headers={"Retry-After": str(_WINDOW_SECONDS)},
                )
        except Exception:
            # Fail open on Redis errors so liveness is preserved.
            pass
        finally:
            await redis_client.aclose()

        return await call_next(request)
