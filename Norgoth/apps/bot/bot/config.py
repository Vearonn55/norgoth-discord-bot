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
    command_sync_mode: str
    test_guild_ids: tuple[int, ...]
    dashboard_url: str

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

        sync_mode = (
            os.getenv("NORBOT_COMMAND_SYNC_MODE", "guild").strip().lower() or "guild"
        )
        if sync_mode not in {"guild", "global"}:
            sync_mode = "guild"

        test_guild_ids: list[int] = []
        raw_guilds = os.getenv("NORBOT_TEST_GUILD_IDS", "").strip()
        if raw_guilds:
            for part in raw_guilds.replace(";", ",").split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    test_guild_ids.append(int(part))
                except ValueError:
                    continue

        dashboard_url = (
            os.getenv("NORGOTH_DASHBOARD_URL", "").strip()
            or os.getenv("NEXT_PUBLIC_DASHBOARD_URL", "").strip()
            or "https://www.norbot.io"
        ).rstrip("/")

        return cls(
            token=token,
            application_id=application_id,
            redis_url=os.getenv("NORGOTH_REDIS_URL", "redis://localhost:6379/0"),
            api_base_url=os.getenv("NORGOTH_API_URL", "http://127.0.0.1:8000"),
            internal_token=internal_token,
            command_sync_mode=sync_mode,
            test_guild_ids=tuple(test_guild_ids),
            dashboard_url=dashboard_url,
        )


def internal_api_headers(settings: BotSettings) -> dict[str, str]:
    """Headers for bot → API internal routes."""

    return {
        "X-Norgoth-Internal-Token": settings.internal_token,
        "X-Norgoth-Bot-Token": settings.internal_token,
    }
