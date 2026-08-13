"""RSS / Atom feed polling worker.

Run:
  python -m app.workers.rss_feed_worker
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

_here = Path(__file__).resolve()
if len(_here.parents) > 4:
    load_dotenv(_here.parents[4] / ".env")
load_dotenv()

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.integrations.discord.bot_rest import DiscordBotClient  # noqa: E402
from app.services.rss import coordinator  # noqa: E402
from app.services.rss.poller import poll_due_feeds  # noqa: E402

logger = logging.getLogger("norgoth.rss.worker")


async def worker_loop() -> None:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required for rss-worker")

    session_factory = get_session_factory()
    timeout = httpx.Timeout(20.0, connect=5.0)

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False
    ) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        tick = 0
        logger.info("rss-worker started")
        while True:
            tick += 1
            try:
                await coordinator.heartbeat()
                processed = await poll_due_feeds(
                    session_factory,
                    bot=bot,
                    http_client=http_client,
                    limit=20,
                )
                if processed:
                    logger.info("rss-worker processed %s feeds", processed)
            except Exception:  # noqa: BLE001
                logger.exception("rss-worker tick failed")
            await asyncio.sleep(5)


def main() -> None:
    logging.basicConfig(
        level=os.getenv("NORGOTH_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
