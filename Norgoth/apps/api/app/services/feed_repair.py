"""Feed Channels Repair: recreate missing channels and sync feed posts."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_TEXT,
    DiscordBotAPIError,
    DiscordBotClient,
    feed_channel_permission_overwrites,
)
from app.services.audit import record_audit
from app.services.campaign_store import get_redis
from app.services.feature_config_store import save_config
from app.services.feed_category import FeedCategoryError, resolve_feed_parent_id
from app.services.feed_ranking import (
    FEED_REFRESH_LOCK_TTL_SEC,
    FEED_WINDOWS,
    FeedWindow,
    clamp_refresh_interval_minutes,
    feed_refresh_lock_key,
    load_merged_feed_config,
    resolve_next_refresh_at,
    schedule_after_failure,
    schedule_after_success,
)
from app.services.feed_rebuild import rebuild_feed_window

logger = logging.getLogger("norgoth.feed.repair")


def _window_channel_name(window: FeedWindow) -> str:
    return f"feed-{window.replace('_', '-')}"


async def acquire_feed_refresh_lock(guild_id: str) -> bool:
    redis = await get_redis()
    try:
        return bool(
            await redis.set(
                feed_refresh_lock_key(guild_id),
                "1",
                nx=True,
                ex=FEED_REFRESH_LOCK_TTL_SEC,
            )
        )
    finally:
        await redis.aclose()


async def release_feed_refresh_lock(guild_id: str) -> None:
    redis = await get_redis()
    try:
        await redis.delete(feed_refresh_lock_key(guild_id))
    finally:
        await redis.aclose()


def _scheduler_payload(
    config: dict[str, Any],
    *,
    scheduler_status: str,
) -> dict[str, Any]:
    from app.services.feed_ranking import scheduler_countdown_fields

    fields = scheduler_countdown_fields(config)
    fields["scheduler_status"] = scheduler_status
    return fields


async def repair_feed_channels(
    session: AsyncSession,
    *,
    guild_id: str,
) -> dict[str, Any]:
    """Idempotent Repair: recreate missing channels, sync posts, structured result."""

    settings = get_settings()
    if not settings.discord_bot_token:
        config = await load_merged_feed_config(guild_id)
        return {
            "success": False,
            "guild_id": guild_id,
            "channels_created": 0,
            "messages_deleted": 0,
            "messages_restored": 0,
            "messages_updated": 0,
            "windows": [],
            "errors": ["Discord bot token not configured."],
            **_scheduler_payload(config, scheduler_status="error"),
        }

    if not await acquire_feed_refresh_lock(guild_id):
        config = await load_merged_feed_config(guild_id)
        logger.info(
            "feed_refresh_skipped guild=%s reason=busy",
            guild_id,
        )
        return {
            "success": False,
            "guild_id": guild_id,
            "channels_created": 0,
            "messages_deleted": 0,
            "messages_restored": 0,
            "messages_updated": 0,
            "windows": [],
            "errors": ["Feed refresh already in progress."],
            **_scheduler_payload(config, scheduler_status="busy"),
        }

    config = await load_merged_feed_config(guild_id)
    interval = clamp_refresh_interval_minutes(config.get("refresh_interval_minutes"))
    logger.info(
        "feed_refresh_started guild=%s interval=%s next=%s",
        guild_id,
        interval,
        resolve_next_refresh_at(config),
    )

    channels_created = 0
    messages_deleted = 0
    messages_restored = 0
    messages_updated = 0
    window_results: list[dict[str, Any]] = []
    errors: list[str] = []
    config_dirty = False

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            bot_user_id: str | None = None
            try:
                me = await bot.get_bot_user()
                bot_user_id = str(me.get("id") or "") or None
            except DiscordBotAPIError as error:
                errors.append(f"Could not resolve bot user: {error}")

            overwrites = feed_channel_permission_overwrites(
                guild_id, bot_user_id=bot_user_id
            )

            parent_id: str | None = None
            try:
                parent_id = await resolve_feed_parent_id(
                    bot, config.get("feed_category_id")
                )
            except FeedCategoryError as error:
                errors.append(error.message)
                logger.warning(
                    "Feed repair: category issue guild=%s code=%s — using guild root",
                    guild_id,
                    error.code,
                )
                if config.get("feed_category_id"):
                    config["feed_category_id"] = None
                    config_dirty = True
                parent_id = None

            for window in FEED_WINDOWS:
                window_cfg = dict(config["windows"].get(window) or {})
                channel_id = window_cfg.get("channel_id")
                should_have_channel = bool(
                    window_cfg.get("enabled")
                    or channel_id
                    or window_cfg.get("norgoth_managed")
                )
                if not should_have_channel:
                    continue

                channel_missing = False
                if channel_id:
                    try:
                        await bot.get_channel(str(channel_id))
                    except DiscordBotAPIError as error:
                        if error.status_code == 404:
                            channel_missing = True
                            logger.info(
                                "Feed repair: channel missing guild=%s window=%s channel=%s",
                                guild_id,
                                window,
                                channel_id,
                            )
                        else:
                            errors.append(
                                f"{window}: channel check failed ({error})"
                            )
                            window_results.append(
                                {
                                    "window": window,
                                    "ok": False,
                                    "reason": "discord_error",
                                    "error": str(error),
                                }
                            )
                            continue
                else:
                    channel_missing = True

                if channel_missing:
                    try:
                        created = await bot.create_guild_channel(
                            guild_id,
                            name=_window_channel_name(window),
                            channel_type=CHANNEL_TYPE_TEXT,
                            parent_id=parent_id,
                            permission_overwrites=overwrites,
                            reason="Norgoth Top Trending repair",
                        )
                        new_id = str(created.get("id") or "") or None
                        if not new_id:
                            errors.append(f"{window}: channel create returned no id")
                            window_results.append(
                                {
                                    "window": window,
                                    "ok": False,
                                    "reason": "create_failed",
                                }
                            )
                            continue
                        window_cfg["channel_id"] = new_id
                        window_cfg["enabled"] = True
                        window_cfg["norgoth_managed"] = True
                        config["windows"][window] = window_cfg
                        config_dirty = True
                        channels_created += 1
                        channel_id = new_id
                        logger.info(
                            "Feed repair: recreated channel guild=%s window=%s channel=%s parent=%s",
                            guild_id,
                            window,
                            new_id,
                            parent_id,
                        )
                    except DiscordBotAPIError as error:
                        errors.append(f"{window}: create failed ({error})")
                        window_results.append(
                            {
                                "window": window,
                                "ok": False,
                                "reason": "create_failed",
                                "error": str(error),
                            }
                        )
                        continue
                else:
                    try:
                        await bot.edit_channel(
                            str(channel_id),
                            parent_id=parent_id,
                            permission_overwrites=overwrites,
                            reason="Norgoth Top Trending repair permissions",
                        )
                    except DiscordBotAPIError as error:
                        errors.append(
                            f"{window}: permission/category update failed ({error})"
                        )

                if config_dirty:
                    await save_config(
                        guild_id,
                        "feed_channels",
                        config,
                        enabled=bool(config.get("enabled")),
                    )
                    config_dirty = False

                result = await rebuild_feed_window(
                    session,
                    guild_id=guild_id,
                    window=window,  # type: ignore[arg-type]
                    config=config,
                    force=True,
                )
                window_results.append(result)
                messages_deleted += int(result.get("messages_deleted") or 0)
                messages_restored += int(result.get("messages_restored") or 0)
                messages_updated += int(result.get("messages_updated") or 0)
                if not result.get("ok"):
                    reason = result.get("reason") or "sync_failed"
                    err = result.get("error")
                    errors.append(
                        f"{window}: {reason}" + (f" ({err})" if err else "")
                    )

        success = True
        if errors and not any(r.get("ok") for r in window_results):
            success = False
        elif window_results and not any(r.get("ok") for r in window_results):
            success = False

        scheduler_status = "scheduled"
        if success or any(r.get("ok") for r in window_results):
            schedule_after_success(config)
            config_dirty = True
            scheduler_status = "scheduled"
            logger.info(
                "feed_refresh_completed guild=%s interval=%s last=%s next=%s",
                guild_id,
                interval,
                config.get("last_full_sync_at"),
                config.get("next_refresh_at"),
            )
        else:
            schedule_after_failure(config)
            config_dirty = True
            scheduler_status = "retrying"
            logger.warning(
                "feed_refresh_failed guild=%s interval=%s next_retry=%s errors=%s",
                guild_id,
                interval,
                config.get("next_refresh_at"),
                errors[:3],
            )

        if config_dirty:
            await save_config(
                guild_id,
                "feed_channels",
                config,
                enabled=bool(config.get("enabled")),
            )

        await record_audit(
            session,
            entity_type="feed_config",
            action="repair",
            guild_id=guild_id,
            changes={
                "channels_created": channels_created,
                "messages_deleted": messages_deleted,
                "messages_restored": messages_restored,
                "messages_updated": messages_updated,
                "last_full_sync_at": config.get("last_full_sync_at"),
                "next_refresh_at": config.get("next_refresh_at"),
                "errors": errors,
            },
        )
        await session.commit()

        return {
            "success": success,
            "guild_id": guild_id,
            "channels_created": channels_created,
            "messages_deleted": messages_deleted,
            "messages_restored": messages_restored,
            "messages_updated": messages_updated,
            "windows": window_results,
            "errors": errors,
            **_scheduler_payload(config, scheduler_status=scheduler_status),
            "feed_category_id": config.get("feed_category_id"),
        }
    finally:
        await release_feed_refresh_lock(guild_id)
