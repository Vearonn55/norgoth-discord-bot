"""Map Discord OAuth failures to stable API HTTP errors."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request

from app.integrations.discord.oauth import DiscordOAuthError

logger = logging.getLogger(__name__)


def raise_discord_oauth_http_error(
    error: DiscordOAuthError,
    *,
    request: Request | None = None,
    route: str = "unknown",
) -> None:
    """Raise an HTTPException with a machine-readable Discord OAuth code.

    Never returns — always raises.
    """

    request_id = "unavailable"
    if request is not None:
        raw = getattr(request.state, "request_id", None)
        if isinstance(raw, str):
            request_id = raw

    status = error.http_status
    logger.warning(
        "Discord OAuth failure: request_id=%s route=%s operation=%s "
        "discord_http_status=%s discord_code=%s",
        request_id,
        route,
        error.operation,
        status,
        error.discord_code,
    )

    headers: dict[str, str] | None = None
    if status == 401 or status == 403:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "discord_token_invalid",
                "message": "Discord authorization expired or was revoked. Please reconnect Discord.",
            },
        )
    if status == 429:
        if error.retry_after:
            headers = {"Retry-After": error.retry_after}
        raise HTTPException(
            status_code=429,
            detail={
                "code": "discord_rate_limited",
                "message": "Discord is rate-limiting guild requests. Please retry shortly.",
            },
            headers=headers,
        )
    if status is not None and status >= 500:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "discord_unavailable",
                "message": "Discord is temporarily unavailable. Please retry.",
            },
        )

    raise HTTPException(
        status_code=502,
        detail={
            "code": "discord_unavailable",
            "message": "Could not load Discord servers. Please retry.",
        },
    )


def http_detail(code: str, message: str) -> dict[str, str]:
    """Build a structured HTTPException detail payload."""

    return {"code": code, "message": message}


def detail_as_mapping(detail: Any) -> dict[str, str] | None:
    """Return code/message from an HTTPException detail when structured."""

    if isinstance(detail, dict):
        code = detail.get("code")
        message = detail.get("message")
        if isinstance(code, str) and isinstance(message, str):
            return {"code": code, "message": message}
    return None
