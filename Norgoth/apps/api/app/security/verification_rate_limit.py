"""Rate-limit helpers for public verification OAuth endpoints."""

from __future__ import annotations

import logging

from app.services.campaign_store import get_redis

logger = logging.getLogger(__name__)

AUTHORIZE_LIMIT = 30
AUTHORIZE_WINDOW_SECONDS = 60
CALLBACK_LIMIT = 60
CALLBACK_WINDOW_SECONDS = 60


class VerificationRateLimitExceeded(Exception):
    """Raised when an OAuth endpoint exceeds its Redis rate limit."""


async def enforce_verification_rate_limit(
    *,
    bucket: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Increment a Redis counter and raise when the limit is exceeded."""

    key = f"norgoth:ratelimit:verification:{bucket}:{identity}"
    redis_client = await get_redis()
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window_seconds)
        if int(count) > limit:
            raise VerificationRateLimitExceeded(
                f"Rate limit exceeded for {bucket}."
            )
    finally:
        await redis_client.aclose()
