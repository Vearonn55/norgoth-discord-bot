"""Per-guild RSS / Atom feed configuration API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.db.session import get_database_session
from app.models.rss_feeds import RssFeedConfig, RssFeedItem
from app.services.audit import record_audit
from app.services.rss.quotas import (
    MAX_FEEDS_PER_GUILD,
    MIN_POLL_INTERVAL_SECONDS,
    clamp_poll_interval,
    feed_url_hash,
    next_poll_after_success,
)
from app.services.rss.service import (
    bootstrap_items,
    probe_feed_url,
    serialize_feed,
)
from app.services.rss import coordinator

SNOWFLAKE = r"^[0-9]{5,25}$"

router = APIRouter(
    tags=["RSS Feeds"],
    dependencies=[Depends(guild_manager_dependency())],
)


class ProbeBody(BaseModel):
    feed_url: str = Field(min_length=8, max_length=2000)


class CreateFeedBody(BaseModel):
    feed_url: str = Field(min_length=8, max_length=2000)
    channel_id: str = Field(pattern=SNOWFLAKE)
    mention_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    display_name: Optional[str] = Field(default=None, max_length=200)
    poll_interval_seconds: int = Field(
        default=300, ge=MIN_POLL_INTERVAL_SECONDS, le=86_400
    )
    enabled: bool = True


class PatchFeedBody(BaseModel):
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    mention_role_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    display_name: Optional[str] = Field(default=None, max_length=200)
    poll_interval_seconds: Optional[int] = Field(
        default=None, ge=MIN_POLL_INTERVAL_SECONDS, le=86_400
    )
    enabled: Optional[bool] = None
    feed_url: Optional[str] = Field(default=None, min_length=8, max_length=2000)
    clear_mention_role: bool = False


@router.get("/guilds/{guild_id}/rss-feeds")
async def list_rss_feeds(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    feeds = (
        await session.scalars(
            select(RssFeedConfig)
            .where(RssFeedConfig.guild_id == guild_id)
            .order_by(RssFeedConfig.created_at.desc())
        )
    ).all()
    online = await coordinator.worker_online()
    return {
        "guild_id": guild_id,
        "feeds": [serialize_feed(f) for f in feeds],
        "max_feeds": MAX_FEEDS_PER_GUILD,
        "worker_online": online,
    }


@router.post("/guilds/{guild_id}/rss-feeds/probe")
async def probe_rss_feed(
    guild_id: str,
    body: ProbeBody,
) -> dict[str, Any]:
    probe = await probe_feed_url(body.feed_url.strip())
    return {
        "guild_id": guild_id,
        "ok": probe.ok,
        "error": probe.error,
        "format_hint": probe.format_hint,
        "feed_title": probe.feed_title,
        "sample_title": probe.sample_title,
        "item_count": probe.item_count,
        "final_url": probe.final_url,
    }


@router.post("/guilds/{guild_id}/rss-feeds", status_code=status.HTTP_201_CREATED)
async def create_rss_feed(
    guild_id: str,
    body: CreateFeedBody,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    count = await session.scalar(
        select(func.count())
        .select_from(RssFeedConfig)
        .where(RssFeedConfig.guild_id == guild_id)
    )
    if count is not None and int(count) >= MAX_FEEDS_PER_GUILD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_FEEDS_PER_GUILD} RSS feeds per server.",
        )

    url = body.feed_url.strip()
    url_hash = feed_url_hash(url)
    dup = await session.scalar(
        select(RssFeedConfig.id).where(
            RssFeedConfig.guild_id == guild_id,
            RssFeedConfig.feed_url_hash == url_hash,
        )
    )
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This feed URL is already configured for this server.",
        )

    probe = await probe_feed_url(url)
    if not probe.ok or probe.parsed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=probe.error or "Feed probe failed.",
        )

    interval = clamp_poll_interval(body.poll_interval_seconds)
    now = datetime.now(timezone.utc)
    feed = RssFeedConfig(
        guild_id=guild_id,
        feed_url=url,
        feed_url_hash=url_hash,
        display_name=(body.display_name or probe.feed_title or None),
        channel_id=body.channel_id,
        mention_role_id=body.mention_role_id,
        enabled=bool(body.enabled),
        poll_interval_seconds=interval,
        format_hint=probe.format_hint,
        etag=probe.etag,
        last_modified=probe.last_modified,
        next_poll_at=next_poll_after_success(interval, now=now)
        if body.enabled
        else None,
        last_success_at=now,
        last_error=None,
        failure_count=0,
    )
    session.add(feed)
    await session.flush()
    await bootstrap_items(session, feed, probe.parsed)
    await record_audit(
        session,
        entity_type="rss_feed_config",
        action="create",
        guild_id=guild_id,
        entity_id=str(feed.id),
        changes={"feed_url": url, "channel_id": body.channel_id},
    )
    await session.commit()
    await session.refresh(feed)
    return serialize_feed(feed)


@router.patch("/guilds/{guild_id}/rss-feeds/{feed_id}")
async def patch_rss_feed(
    guild_id: str,
    feed_id: UUID = Path(...),
    body: PatchFeedBody = ...,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    feed = await session.scalar(
        select(RssFeedConfig).where(
            RssFeedConfig.id == feed_id,
            RssFeedConfig.guild_id == guild_id,
        )
    )
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    changes: dict[str, Any] = {}
    url_changed = False

    if body.feed_url is not None and body.feed_url.strip() != feed.feed_url:
        url = body.feed_url.strip()
        url_hash = feed_url_hash(url)
        dup = await session.scalar(
            select(RssFeedConfig.id).where(
                RssFeedConfig.guild_id == guild_id,
                RssFeedConfig.feed_url_hash == url_hash,
                RssFeedConfig.id != feed.id,
            )
        )
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This feed URL is already configured for this server.",
            )
        probe = await probe_feed_url(url)
        if not probe.ok or probe.parsed is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=probe.error or "Feed probe failed.",
            )
        changes["feed_url"] = {"from": feed.feed_url, "to": url}
        feed.feed_url = url
        feed.feed_url_hash = url_hash
        feed.format_hint = probe.format_hint
        feed.etag = probe.etag
        feed.last_modified = probe.last_modified
        await session.execute(
            delete(RssFeedItem).where(RssFeedItem.feed_id == feed.id)
        )
        await session.flush()
        await bootstrap_items(session, feed, probe.parsed)
        url_changed = True

    if body.channel_id is not None and body.channel_id != feed.channel_id:
        changes["channel_id"] = {"from": feed.channel_id, "to": body.channel_id}
        feed.channel_id = body.channel_id

    if body.clear_mention_role:
        if feed.mention_role_id is not None:
            changes["mention_role_id"] = {
                "from": feed.mention_role_id,
                "to": None,
            }
        feed.mention_role_id = None
    elif body.mention_role_id is not None:
        changes["mention_role_id"] = {
            "from": feed.mention_role_id,
            "to": body.mention_role_id,
        }
        feed.mention_role_id = body.mention_role_id

    if body.display_name is not None:
        changes["display_name"] = {
            "from": feed.display_name,
            "to": body.display_name or None,
        }
        feed.display_name = body.display_name or None

    if body.poll_interval_seconds is not None:
        interval = clamp_poll_interval(body.poll_interval_seconds)
        changes["poll_interval_seconds"] = {
            "from": feed.poll_interval_seconds,
            "to": interval,
        }
        feed.poll_interval_seconds = interval

    if body.enabled is not None and body.enabled != feed.enabled:
        changes["enabled"] = {"from": feed.enabled, "to": body.enabled}
        feed.enabled = body.enabled
        if body.enabled:
            feed.next_poll_at = next_poll_after_success(
                int(feed.poll_interval_seconds or 300)
            )
        else:
            feed.next_poll_at = None

    action = "update"
    if "enabled" in changes:
        action = "enable" if feed.enabled else "disable"

    await record_audit(
        session,
        entity_type="rss_feed_config",
        action=action,
        guild_id=guild_id,
        entity_id=str(feed.id),
        changes=changes or {"url_changed": url_changed},
    )
    await session.commit()
    await session.refresh(feed)
    return serialize_feed(feed)


@router.delete("/guilds/{guild_id}/rss-feeds/{feed_id}", status_code=204)
async def delete_rss_feed(
    guild_id: str,
    feed_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> None:
    feed = await session.scalar(
        select(RssFeedConfig).where(
            RssFeedConfig.id == feed_id,
            RssFeedConfig.guild_id == guild_id,
        )
    )
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    await record_audit(
        session,
        entity_type="rss_feed_config",
        action="delete",
        guild_id=guild_id,
        entity_id=str(feed.id),
        changes={"feed_url": feed.feed_url},
    )
    await session.delete(feed)
    await session.commit()


@router.post("/guilds/{guild_id}/rss-feeds/{feed_id}/test")
async def test_rss_feed(
    guild_id: str,
    feed_id: UUID = Path(...),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Force an immediate poll (publish new items only; respects bootstrap)."""

    from app.core.config import get_settings
    from app.integrations.discord.bot_rest import DiscordBotClient
    import httpx
    from app.services.rss.poller import process_feed

    feed = await session.scalar(
        select(RssFeedConfig).where(
            RssFeedConfig.id == feed_id,
            RssFeedConfig.guild_id == guild_id,
        )
    )
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(
            status_code=503, detail="Bot token is not configured."
        )

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        bot = DiscordBotClient(settings.discord_bot_token, client)
        # Temporarily due so process_feed runs publish path.
        feed.next_poll_at = datetime.now(timezone.utc)
        stats = await process_feed(session, feed, bot=bot, http_client=client)
        await session.commit()

    return {"guild_id": guild_id, "feed_id": str(feed_id), **stats}
