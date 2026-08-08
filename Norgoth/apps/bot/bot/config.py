"""Bot configuration loaded from the product-level .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Norgoth/.env is two levels above apps/bot/.
PRODUCT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class BotSettings:
    token: str
    application_id: int | None
    redis_url: str
    api_base_url: str

    @classmethod
    def from_environment(cls) -> "BotSettings":
        load_dotenv(PRODUCT_ROOT / ".env")

        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

        if not token:
            raise RuntimeError(
                "DISCORD_BOT_TOKEN is not set. Add it to Norgoth/.env "
                "(see Norgoth/.env.example)."
            )

        raw_application_id = os.getenv("DISCORD_APPLICATION_ID", "").strip()
        application_id = int(raw_application_id) if raw_application_id else None

        return cls(
            token=token,
            application_id=application_id,
            redis_url=os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0"),
            api_base_url=os.getenv("NORGOTH_API_URL", "http://127.0.0.1:8000"),
        )
