"""Bot configuration loaded from environment (and optional local .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_local_dotenv() -> None:
    """Load Norgoth/.env in monorepo checkouts; no-op in shallow Docker layouts."""

    here = Path(__file__).resolve()
    # Local: Norgoth/apps/bot/bot/config.py -> parents[3] == Norgoth/
    if len(here.parents) > 3:
        load_dotenv(here.parents[3] / ".env")
    load_dotenv()


@dataclass(frozen=True, slots=True)
class BotSettings:
    token: str
    application_id: int | None
    redis_url: str
    api_base_url: str
    internal_token: str

    @classmethod
    def from_environment(cls) -> "BotSettings":
        _load_local_dotenv()

        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

        if not token:
            raise RuntimeError(
                "DISCORD_BOT_TOKEN is not set. Add it to Norgoth/.env "
                "(see Norgoth/.env.example) or the container env file."
            )

        raw_application_id = os.getenv("DISCORD_APPLICATION_ID", "").strip()
        application_id = int(raw_application_id) if raw_application_id else None
        internal_token = os.getenv("NORGOTH_INTERNAL_TOKEN", "").strip() or token

        return cls(
            token=token,
            application_id=application_id,
            redis_url=os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0"),
            api_base_url=os.getenv("NORGOTH_API_URL", "http://127.0.0.1:8000"),
            internal_token=internal_token,
        )


def internal_api_headers(settings: BotSettings) -> dict[str, str]:
    """Headers for bot → API internal routes."""

    return {
        "X-Norgoth-Internal-Token": settings.internal_token,
        "X-Norgoth-Bot-Token": settings.internal_token,
    }
