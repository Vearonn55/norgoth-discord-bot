"""Reject oversized request bodies before handlers allocate them."""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MiB for JSON/API payloads
UPLOAD_MAX_BYTES = 20 * 1024 * 1024  # matches nginx client_max_body_size


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        header = request.headers.get("content-length")
        if header:
            try:
                length = int(header)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
            limit = (
                UPLOAD_MAX_BYTES
                if "/uploads/" in request.url.path
                else MAX_BODY_BYTES
            )
            if length > limit:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
        return await call_next(request)
