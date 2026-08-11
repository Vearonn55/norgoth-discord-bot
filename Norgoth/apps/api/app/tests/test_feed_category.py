"""Feed category parent resolution helpers."""

from __future__ import annotations

import pytest

from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_CATEGORY,
    CHANNEL_TYPE_TEXT,
    DiscordBotAPIError,
)
from app.services.feed_category import (
    FeedCategoryError,
    resolve_feed_parent_id,
)


class FakeBot:
    def __init__(self, channels: dict[str, dict]) -> None:
        self.channels = channels

    async def get_channel(self, channel_id: str) -> dict:
        if channel_id not in self.channels:
            raise DiscordBotAPIError("missing", status_code=404)
        return self.channels[channel_id]


@pytest.mark.anyio
async def test_resolve_parent_none_when_unset() -> None:
    bot = FakeBot({})
    assert await resolve_feed_parent_id(bot, None) is None
    assert await resolve_feed_parent_id(bot, "") is None


@pytest.mark.anyio
async def test_resolve_parent_valid_category() -> None:
    bot = FakeBot({"99": {"id": "99", "type": CHANNEL_TYPE_CATEGORY, "name": "Feeds"}})
    assert await resolve_feed_parent_id(bot, "99") == "99"


@pytest.mark.anyio
async def test_resolve_parent_missing_raises() -> None:
    bot = FakeBot({})
    with pytest.raises(FeedCategoryError) as exc:
        await resolve_feed_parent_id(bot, "404")
    assert exc.value.code == "category_missing"


@pytest.mark.anyio
async def test_resolve_parent_rejects_text_channel() -> None:
    bot = FakeBot({"1": {"id": "1", "type": CHANNEL_TYPE_TEXT, "name": "general"}})
    with pytest.raises(FeedCategoryError) as exc:
        await resolve_feed_parent_id(bot, "1")
    assert exc.value.code == "category_invalid"
