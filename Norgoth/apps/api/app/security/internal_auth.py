"""Shared authentication for bot/worker → API internal routes."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException

from app.core.config import Settings, get_settings


def _tokens_match(provided: str | None, expected: str | None) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def is_valid_internal_token(provided: str | None, settings: Settings | None = None) -> bool:
    """Accept NORGOTH_INTERNAL_TOKEN, with Discord bot token as a migrate fallback."""

    resolved = settings or get_settings()
    if _tokens_match(provided, resolved.internal_token):
        return True
    # Dual-accept during the cutover window so bot deploys can lag the API.
    return _tokens_match(provided, resolved.discord_bot_token)


async def require_internal_token(
    x_norgoth_internal_token: Annotated[str | None, Header()] = None,
    x_norgoth_bot_token: Annotated[str | None, Header()] = None,
) -> None:
    """Guard internal endpoints with the dedicated internal token.

    ``X-Norgoth-Bot-Token`` remains accepted during migration so existing bot
    callers keep working until they switch to ``X-Norgoth-Internal-Token``.
    """

    settings = get_settings()
    provided = x_norgoth_internal_token or x_norgoth_bot_token
    if not is_valid_internal_token(provided, settings):
        raise HTTPException(status_code=401, detail="Invalid internal token.")


# Back-compat alias used by existing routers.
require_bot_token = require_internal_token
