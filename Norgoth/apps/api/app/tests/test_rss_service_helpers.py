"""RSS service helper tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.rss.parser import FeedItem, ParsedFeed
from app.services.rss.service import bootstrap_items, clamp_display_name


def test_clamp_display_name_truncates_long_titles() -> None:
    long_title = "A" * 250
    result = clamp_display_name(long_title)
    assert result is not None
    assert len(result) == 200
    assert result.endswith("…")


def test_clamp_display_name_passes_short_values() -> None:
    assert clamp_display_name("AI") == "AI"
    assert clamp_display_name(None) is None


@pytest.mark.asyncio
async def test_bootstrap_items_bulk_skips_existing() -> None:
    session = AsyncMock()
    feed = MagicMock()
    feed.id = "feed-id"
    parsed = ParsedFeed(
        format_hint="rss20",
        title="T",
        items=[
            FeedItem(
                item_key="id:1",
                title="One",
                link=None,
                published=None,
                summary_text="",
                author=None,
            ),
            FeedItem(
                item_key="id:2",
                title="Two",
                link=None,
                published=None,
                summary_text="",
                author=None,
            ),
        ],
    )

    async def _scalars(_query):
        result = MagicMock()
        result.all = MagicMock(return_value=["id:1"])
        return result

    session.scalars = _scalars
    session.add = MagicMock()
    session.flush = AsyncMock()

    inserted = await bootstrap_items(session, feed, parsed)

    assert inserted == 1
    assert session.add.call_count == 1
