"""Request context and standard response-header middleware."""

import re
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

REQUEST_ID_HEADER = "X-Request-ID"

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def resolve_request_id(candidate: str | None) -> str:
    """Return a safe caller-provided request ID or generate a new one."""

    if candidate is not None:
        normalized_candidate = candidate.strip()

        if _REQUEST_ID_PATTERN.fullmatch(normalized_candidate) is not None:
            return normalized_candidate

    return str(uuid4())


def apply_standard_response_headers(
    response: Response,
    *,
    request_id: str,
) -> None:
    """Apply standard API tracing and browser security headers."""

    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Establish a request ID and standard response headers."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process one HTTP request through the application."""

        request_id = resolve_request_id(
            request.headers.get(REQUEST_ID_HEADER),
        )
        request.state.request_id = request_id

        response = await call_next(request)

        apply_standard_response_headers(
            response,
            request_id=request_id,
        )

        return response
