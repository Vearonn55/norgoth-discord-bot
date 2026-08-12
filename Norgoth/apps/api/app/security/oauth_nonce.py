"""One-time OAuth state nonce consumption (Redis)."""

from __future__ import annotations

import logging

from app.services.campaign_store import get_redis

logger = logging.getLogger(__name__)

NONCE_KEY_PREFIX = "norgoth:oauth:state:"
DEFAULT_TTL_SECONDS = 600


class OAuthNonceReplayError(ValueError):
    """Raised when an OAuth state nonce was already consumed."""


async def consume_oauth_nonce(
    nonce: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Mark a nonce as used. Fail closed if Redis is unavailable."""

    if not nonce:
        raise OAuthNonceReplayError("OAuth state nonce is missing.")

    key = f"{NONCE_KEY_PREFIX}{nonce}"
    redis_client = await get_redis()
    try:
        created = await redis_client.set(key, "1", nx=True, ex=max(ttl_seconds, 1))
        if not created:
            raise OAuthNonceReplayError("OAuth state has already been used.")
    finally:
        await redis_client.aclose()
