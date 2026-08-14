"""Shared CORS origin allowlist for credentialed dashboard requests."""

from __future__ import annotations

import os

from app.core.config import Settings


def cors_allow_origins(settings: Settings) -> list[str]:
    """Build the credentialed CORS allowlist for the current environment."""

    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://www.norbot.io",
        "https://norbot.io",
        "https://test.norbot.io",
    ]
    if settings.dashboard_public_url:
        defaults.append(settings.dashboard_public_url.rstrip("/"))

    extra = os.getenv("NORGOTH_CORS_ORIGINS", "").strip()
    if extra:
        defaults.extend(
            origin.strip().rstrip("/")
            for origin in extra.split(",")
            if origin.strip()
        )

    seen: set[str] = set()
    origins: list[str] = []
    for origin in defaults:
        if origin and origin not in seen:
            seen.add(origin)
            origins.append(origin)
    return origins
