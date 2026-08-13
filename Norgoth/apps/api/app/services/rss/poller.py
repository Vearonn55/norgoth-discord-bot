"""Poll a single RSS feed: fetch, dedupe, publish, schedule."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.models.rss_feeds import RssFeedConfig, RssFeedItem
from app.security.ssrf import SsrfError, safe_fetch
from app.services.rss.parser import FeedParseError, parse_feed
from app.services.rss.publisher import publish_item
from app.services.rss.quotas import (
    CLAIM_TTL_SECONDS,
    MAX_POSTS_PER_POLL,
    next_poll_after_failure,
    next_poll_after_success,
)
from app.services.rss.service import bootstrap_items, prune_old_items
from app.services.rss import coordinator

logger = logging.getLogger("norgoth.rss.poll")


async def _module_enabled(guild_id: str) -> bool:
    """Modules default to enabled when the key is missing."""

    try:
        client = await coordinator.get_redis()
        try:
            raw = await client.get(f"norgoth:guild:{guild_id}:modules")
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001
        return True
    if not raw:
        return True
    try:
        import json

        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001
        return True
    if not isinstance(parsed, dict):
        return True
    return bool(parsed.get("rss_feeds", True))


async def process_feed(
    session: AsyncSession,
    feed: RssFeedConfig,
    *,
    bot: DiscordBotClient,
    http_client: httpx.AsyncClient,
    publish: bool = True,
) -> dict[str, int | str | None]:
    """Run one poll cycle. When publish=False, only bootstrap/schedule."""

    now = datetime.now(timezone.utc)
    posted = 0
    seen_new = 0
    skipped_overflow = 0

    try:
        result = await safe_fetch(
            feed.feed_url,
            etag=feed.etag,
            last_modified=feed.last_modified,
            client=http_client,
        )
    except (SsrfError, httpx.HTTPError) as exc:
        feed.failure_count = int(feed.failure_count or 0) + 1
        feed.last_error = str(exc)[:1000]
        feed.next_poll_at = next_poll_after_failure(
            feed.failure_count, int(feed.poll_interval_seconds or 300), now=now
        )
        await session.flush()
        return {"posted": 0, "error": str(exc)}

    if result.status_code == 304:
        feed.failure_count = 0
        feed.last_error = None
        feed.last_success_at = now
        feed.next_poll_at = next_poll_after_success(
            int(feed.poll_interval_seconds or 300), now=now
        )
        await session.flush()
        return {"posted": 0, "error": None, "not_modified": 1}

    if result.status_code >= 400:
        feed.failure_count = int(feed.failure_count or 0) + 1
        feed.last_error = f"HTTP {result.status_code}"[:1000]
        feed.next_poll_at = next_poll_after_failure(
            feed.failure_count, int(feed.poll_interval_seconds or 300), now=now
        )
        await session.flush()
        return {"posted": 0, "error": feed.last_error}

    try:
        parsed = parse_feed(result.body)
    except FeedParseError as exc:
        feed.failure_count = int(feed.failure_count or 0) + 1
        feed.last_error = str(exc)[:1000]
        feed.next_poll_at = next_poll_after_failure(
            feed.failure_count, int(feed.poll_interval_seconds or 300), now=now
        )
        await session.flush()
        return {"posted": 0, "error": str(exc)}

    feed.etag = result.headers.get("etag") or feed.etag
    feed.last_modified = result.headers.get("last-modified") or feed.last_modified
    feed.format_hint = parsed.format_hint

    # First successful parse with no prior items → bootstrap only.
    prior_count = await session.scalar(
        select(RssFeedItem.id).where(RssFeedItem.feed_id == feed.id).limit(1)
    )
    if prior_count is None:
        await bootstrap_items(session, feed, parsed)
        feed.failure_count = 0
        feed.last_error = None
        feed.last_success_at = now
        feed.next_poll_at = next_poll_after_success(
            int(feed.poll_interval_seconds or 300), now=now
        )
        if not feed.display_name and parsed.title:
            feed.display_name = parsed.title[:200]
        await session.flush()
        return {"posted": 0, "bootstrapped": len(parsed.items), "error": None}

    # Existing feed: find unseen items, oldest first.
    existing_keys = set(
        await session.scalars(
            select(RssFeedItem.item_key).where(RssFeedItem.feed_id == feed.id)
        )
    )
    new_items = [item for item in parsed.items if item.item_key not in existing_keys]
    new_items.sort(
        key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc)
    )

    feed_title = feed.display_name or parsed.title
    for item in new_items:
        if publish and posted < MAX_POSTS_PER_POLL:
            try:
                message_id = await publish_item(
                    bot,
                    channel_id=feed.channel_id,
                    item=item,
                    feed_title=feed_title,
                    mention_role_id=feed.mention_role_id,
                )
                session.add(
                    RssFeedItem(
                        feed_id=feed.id,
                        item_key=item.item_key,
                        published_at=item.published,
                        first_seen_at=now,
                        posted_message_id=message_id,
                        skipped_reason=None,
                    )
                )
                posted += 1
                seen_new += 1
            except DiscordBotAPIError as exc:
                feed.failure_count = int(feed.failure_count or 0) + 1
                feed.last_error = f"Discord publish failed: {exc}"[:1000]
                feed.next_poll_at = next_poll_after_failure(
                    feed.failure_count,
                    int(feed.poll_interval_seconds or 300),
                    now=now,
                )
                await session.flush()
                return {
                    "posted": posted,
                    "error": feed.last_error,
                }
        else:
            session.add(
                RssFeedItem(
                    feed_id=feed.id,
                    item_key=item.item_key,
                    published_at=item.published,
                    first_seen_at=now,
                    skipped_reason="overflow" if publish else "bootstrap",
                )
            )
            skipped_overflow += 1
            seen_new += 1

    await prune_old_items(session, feed.id)
    feed.failure_count = 0
    feed.last_error = None
    feed.last_success_at = now
    feed.next_poll_at = next_poll_after_success(
        int(feed.poll_interval_seconds or 300), now=now
    )
    await session.flush()
    return {
        "posted": posted,
        "seen_new": seen_new,
        "overflow": skipped_overflow,
        "error": None,
    }


async def poll_due_feeds(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    bot: DiscordBotClient,
    http_client: httpx.AsyncClient,
    limit: int = 20,
) -> int:
    """Claim and process due enabled feeds. Returns number processed."""

    now = datetime.now(timezone.utc)
    processed = 0
    async with session_factory() as session:
        feeds = (
            await session.scalars(
                select(RssFeedConfig)
                .where(
                    RssFeedConfig.enabled.is_(True),
                    RssFeedConfig.next_poll_at.is_not(None),
                    RssFeedConfig.next_poll_at <= now,
                )
                .order_by(RssFeedConfig.next_poll_at.asc())
                .limit(limit)
            )
        ).all()
        feed_ids = [str(f.id) for f in feeds]

    for feed_id in feed_ids:
        claimed = await coordinator.claim_feed(
            feed_id, ttl_seconds=CLAIM_TTL_SECONDS
        )
        if not claimed:
            continue
        try:
            async with session_factory() as session:
                feed = await session.get(RssFeedConfig, UUID(feed_id))
                if (
                    feed is None
                    or not feed.enabled
                    or feed.next_poll_at is None
                    or feed.next_poll_at > datetime.now(timezone.utc)
                ):
                    continue
                if not await _module_enabled(feed.guild_id):
                    continue
                stats = await process_feed(
                    session, feed, bot=bot, http_client=http_client
                )
                await session.commit()
                processed += 1
                if stats.get("error"):
                    logger.info(
                        "rss poll feed=%s error=%s",
                        feed_id,
                        stats.get("error"),
                    )
                else:
                    logger.debug(
                        "rss poll feed=%s posted=%s",
                        feed_id,
                        stats.get("posted"),
                    )
        except Exception:  # noqa: BLE001
            logger.exception("rss poll failed feed=%s", feed_id)
        finally:
            await coordinator.release_feed_claim(feed_id)

    return processed
