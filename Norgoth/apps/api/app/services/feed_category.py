"""Feed category parent resolution and channel moves."""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_CATEGORY,
    DiscordBotAPIError,
    DiscordBotClient,
)
from app.services.feed_ranking import FEED_WINDOWS

logger = logging.getLogger("norgoth.feed.category")


class FeedCategoryError(Exception):
    """Actionable category configuration error (not a raw Discord 500)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def resolve_feed_parent_id(
    bot: DiscordBotClient,
    category_id: str | None,
) -> str | None:
    """Validate configured category; return parent_id or None for guild root.

    Raises FeedCategoryError when a configured id is missing or not a category.
    """

    if not category_id:
        return None
    try:
        channel = await bot.get_channel(str(category_id))
    except DiscordBotAPIError as error:
        if error.status_code == 404:
            raise FeedCategoryError(
                "category_missing",
                f"Feed category {category_id} no longer exists in Discord. "
                "Choose another category or clear the selection.",
            ) from error
        raise FeedCategoryError(
            "category_check_failed",
            f"Could not verify feed category {category_id}: {error}",
        ) from error

    channel_type = channel.get("type")
    if channel_type != CHANNEL_TYPE_CATEGORY:
        raise FeedCategoryError(
            "category_invalid",
            f"Channel {category_id} is not a Discord category (type={channel_type}).",
        )
    return str(category_id)


async def move_feed_channels_to_category(
    bot: DiscordBotClient,
    *,
    guild_id: str,
    config: dict[str, Any],
    parent_id: str | None,
) -> list[str]:
    """Move existing feed window channels under parent_id (or root). Idempotent."""

    moved: list[str] = []
    for window in FEED_WINDOWS:
        window_cfg = config.get("windows", {}).get(window) or {}
        channel_id = window_cfg.get("channel_id")
        if not channel_id:
            continue
        try:
            await bot.edit_channel(
                str(channel_id),
                parent_id=parent_id,
                reason="Norgoth Feed Channels category update",
            )
            moved.append(str(channel_id))
            logger.info(
                "Feed category: moved channel guild=%s window=%s channel=%s parent=%s",
                guild_id,
                window,
                channel_id,
                parent_id,
            )
        except DiscordBotAPIError as error:
            if error.status_code == 404:
                logger.warning(
                    "Feed category: skip missing channel guild=%s window=%s channel=%s",
                    guild_id,
                    window,
                    channel_id,
                )
                continue
            raise
    return moved
