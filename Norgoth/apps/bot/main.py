"""Norgoth bot entrypoint: python main.py (from Norgoth/apps/bot)."""

from __future__ import annotations

import logging

from bot.client import NorgothBot
from bot.config import BotSettings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    settings = BotSettings.from_environment()
    bot = NorgothBot(settings)
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
