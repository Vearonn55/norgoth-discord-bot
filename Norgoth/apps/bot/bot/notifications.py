"""Stream/content notifications cog — retired in favor of the API worker.

Legacy Redis poller kept disabled. Detection and Discord webhook delivery are
owned by `app.workers.content_notification_worker`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.notifications")


class NotificationsCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        logger.info(
            "NotificationsCog loaded in bridge mode — "
            "content notification worker owns monitoring/delivery."
        )
