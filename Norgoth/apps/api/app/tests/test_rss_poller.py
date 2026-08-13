"""RSS poller behavior: bootstrap, 304, overflow cap."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.rss.parser import FeedItem, ParsedFeed
from app.services.rss.poller import process_feed
from app.services.rss.quotas import MAX_POSTS_PER_POLL


def _feed(**overrides):
    base = {
        "id": uuid4(),
        "guild_id": "123",
        "feed_url": "https://example.com/feed.xml",
        "display_name": "Example",
        "channel_id": "999",
        "mention_role_id": None,
        "enabled": True,
        "poll_interval_seconds": 300,
        "format_hint": None,
        "etag": None,
        "last_modified": None,
        "next_poll_at": datetime.now(timezone.utc),
        "last_success_at": None,
        "last_error": None,
        "failure_count": 0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_process_feed_not_modified(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = _feed(etag='"abc"')
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=1)
    session.scalars = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    result = SimpleNamespace(
        status_code=304,
        headers={},
        body=b"",
        final_url=feed.feed_url,
    )
    monkeypatch.setattr(
        "app.services.rss.poller.safe_fetch",
        AsyncMock(return_value=result),
    )

    bot = AsyncMock()
    http = AsyncMock()
    stats = await process_feed(session, feed, bot=bot, http_client=http)
    assert stats.get("not_modified") == 1
    assert feed.failure_count == 0
    assert feed.next_poll_at is not None


@pytest.mark.asyncio
async def test_bootstrap_when_no_prior_items(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = _feed()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.add = MagicMock()

    parsed = ParsedFeed(
        format_hint="rss20",
        title="T",
        items=[
            FeedItem(
                item_key="id:1",
                title="One",
                link="https://example.com/1",
                published=None,
                summary_text="s",
                author=None,
            )
        ],
    )
    result = SimpleNamespace(
        status_code=200,
        headers={"etag": '"x"'},
        body=b"<rss/>",
        final_url=feed.feed_url,
    )
    monkeypatch.setattr(
        "app.services.rss.poller.safe_fetch",
        AsyncMock(return_value=result),
    )
    monkeypatch.setattr(
        "app.services.rss.poller.parse_feed",
        lambda body: parsed,
    )
    bootstrap = AsyncMock(return_value=1)
    monkeypatch.setattr("app.services.rss.poller.bootstrap_items", bootstrap)

    bot = AsyncMock()
    stats = await process_feed(session, feed, bot=bot, http_client=AsyncMock())
    assert stats.get("bootstrapped") == 1
    assert stats.get("posted") == 0
    bootstrap.assert_awaited()


@pytest.mark.asyncio
async def test_overflow_marks_seen_without_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feed = _feed()
    session = AsyncMock()
    # prior exists
    session.scalar = AsyncMock(return_value=uuid4())
    session.scalars = AsyncMock(
        return_value=SimpleNamespace(all=lambda: [])
    )
    # emulate scalars(). returning empty set of keys via await session.scalars -> result
    async def scalars_side_effect(stmt):  # noqa: ANN001
        return SimpleNamespace(__aiter__=None, all=lambda: [])

    # session.scalars is awaited and then used as await session.scalars(...) which
    # in SQLAlchemy returns a Result; poller uses `await session.scalars(select...)`
    # then the result is passed to set() via `set(await session.scalars(...))` —
    # actually code is: `existing_keys = set(await session.scalars(...))`
    # In SQLAlchemy 2, scalars returns ScalarResult which is iterable.
    session.scalars = AsyncMock(return_value=[])
    session.flush = AsyncMock()
    added = []
    session.add = lambda obj: added.append(obj)

    items = [
        FeedItem(
            item_key=f"id:{i}",
            title=f"T{i}",
            link=f"https://example.com/{i}",
            published=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
            summary_text="",
            author=None,
        )
        for i in range(MAX_POSTS_PER_POLL + 3)
    ]
    parsed = ParsedFeed(format_hint="rss20", title="T", items=items)
    result = SimpleNamespace(
        status_code=200,
        headers={},
        body=b"<rss/>",
        final_url=feed.feed_url,
    )
    monkeypatch.setattr(
        "app.services.rss.poller.safe_fetch",
        AsyncMock(return_value=result),
    )
    monkeypatch.setattr("app.services.rss.poller.parse_feed", lambda body: parsed)
    monkeypatch.setattr(
        "app.services.rss.poller.prune_old_items", AsyncMock()
    )
    monkeypatch.setattr(
        "app.services.rss.poller.publish_item",
        AsyncMock(return_value="111"),
    )

    bot = AsyncMock()
    stats = await process_feed(session, feed, bot=bot, http_client=AsyncMock())
    assert stats["posted"] == MAX_POSTS_PER_POLL
    assert stats["overflow"] == 3
    overflow = [a for a in added if getattr(a, "skipped_reason", None) == "overflow"]
    assert len(overflow) == 3
