"""Feed Channels configuration and rebuild API."""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.config import get_settings
from app.db.session import get_database_session
from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_TEXT,
    DiscordBotAPIError,
    DiscordBotClient,
    feed_channel_permission_overwrites,
)
from app.models.feed_channels import FeedMessage, FeedVote
from app.services.audit import record_audit
from app.services.feature_config_store import save_config
from app.services.feed_category import (
    FeedCategoryError,
    move_feed_channels_to_category,
    resolve_feed_parent_id,
)
from app.services.feed_ranking import (
    FEED_WINDOWS,
    FeedWindow,
    clamp_display_limit,
    clamp_refresh_interval_minutes,
    compute_next_refresh_at,
    emoji_reaction_key,
    emojis_equal,
    load_merged_feed_config,
    merge_feed_config,
    parse_iso_utc,
    touch_last_full_sync,
)
from app.services.feed_rebuild import process_dirty_feeds
from app.services.feed_repair import repair_feed_channels

logger = logging.getLogger("norgoth.feed.routes")

SNOWFLAKE = r"^[0-9]{5,25}$"

router = APIRouter(
    tags=["Feed Channels"],
    dependencies=[Depends(guild_manager_dependency())],
)


class FeedEmojiBody(BaseModel):
    kind: Literal["unicode", "custom"] = "unicode"
    id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    name: str = Field(min_length=1, max_length=64)
    animated: bool = False
    reaction: str = Field(min_length=1, max_length=128)


class FeedWindowBody(BaseModel):
    enabled: bool = False
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    norgoth_managed: bool = False


class FeedConfigBody(BaseModel):
    enabled: bool = False
    upvote_emoji: FeedEmojiBody
    downvote_emoji: FeedEmojiBody
    source_channel_ids: list[str] = Field(default_factory=list, max_length=100)
    excluded_channel_ids: list[str] = Field(default_factory=list, max_length=100)
    min_net_score: int = Field(default=1, ge=0, le=10_000)
    display_limit: int = Field(default=10, ge=1, le=25)
    refresh_interval_minutes: int = Field(default=15, ge=5, le=60)
    feed_category_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    exclude_bots: bool = True
    exclude_webhooks: bool = True
    exclude_threads: bool = True
    windows: dict[str, FeedWindowBody] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_emojis(self) -> "FeedConfigBody":
        if emojis_equal(self.upvote_emoji.model_dump(), self.downvote_emoji.model_dump()):
            raise ValueError("Upvote and downvote emojis must be different.")
        if not emoji_reaction_key(self.upvote_emoji.model_dump()):
            raise ValueError("Invalid upvote emoji.")
        if not emoji_reaction_key(self.downvote_emoji.model_dump()):
            raise ValueError("Invalid downvote emoji.")
        return self


class FeedStateBody(BaseModel):
    enabled: bool


class FeedWindowPatchBody(BaseModel):
    enabled: Optional[bool] = None
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE)
    norgoth_managed: Optional[bool] = None


def _normalize_payload(body: FeedConfigBody) -> dict[str, Any]:
    windows = {
        key: {"enabled": False, "channel_id": None, "norgoth_managed": False}
        for key in FEED_WINDOWS
    }
    for key, value in body.windows.items():
        if key not in windows:
            continue
        windows[key] = {
            "enabled": value.enabled,
            "channel_id": value.channel_id,
            "norgoth_managed": value.norgoth_managed,
        }
        # A channel id implies configured; enabling without channel stays unusable.
        if value.channel_id and value.enabled is False:
            pass
    return {
        "enabled": body.enabled,
        "upvote_emoji": body.upvote_emoji.model_dump(),
        "downvote_emoji": body.downvote_emoji.model_dump(),
        "source_channel_ids": list(dict.fromkeys(body.source_channel_ids)),
        "excluded_channel_ids": list(dict.fromkeys(body.excluded_channel_ids)),
        "min_net_score": body.min_net_score,
        "display_limit": clamp_display_limit(body.display_limit),
        "refresh_interval_minutes": clamp_refresh_interval_minutes(
            body.refresh_interval_minutes
        ),
        "feed_category_id": body.feed_category_id,
        "exclude_bots": body.exclude_bots,
        "exclude_webhooks": body.exclude_webhooks,
        "exclude_threads": body.exclude_threads,
        "windows": windows,
    }


@router.get("/guilds/{guild_id}/feed-channels/config")
async def get_feed_config(
    guild_id: str = Path(pattern=SNOWFLAKE),
) -> dict[str, Any]:
    config = await load_merged_feed_config(guild_id)
    return {
        "guild_id": guild_id,
        "config": config,
        "next_refresh_at": compute_next_refresh_at(
            config.get("last_full_sync_at"),
            config.get("refresh_interval_minutes"),
        ),
    }


@router.put("/guilds/{guild_id}/feed-channels/config")
async def put_feed_config(
    body: FeedConfigBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    previous = await load_merged_feed_config(guild_id)
    payload = _normalize_payload(body)
    payload["last_refresh_at"] = previous.get("last_refresh_at") or {}
    payload["last_full_sync_at"] = previous.get("last_full_sync_at")

    prev_interval = clamp_refresh_interval_minutes(
        previous.get("refresh_interval_minutes")
    )
    new_interval = payload["refresh_interval_minutes"]
    if new_interval != prev_interval:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        last = parse_iso_utc(payload.get("last_full_sync_at"))
        if last is None or last + timedelta(minutes=new_interval) <= now:
            touch_last_full_sync(payload, now=now)
        logger.info(
            "Feed refresh interval changed guild=%s from=%s to=%s last_full_sync_at=%s",
            guild_id,
            prev_interval,
            new_interval,
            payload.get("last_full_sync_at"),
        )

    prev_category = previous.get("feed_category_id") or None
    new_category = payload.get("feed_category_id") or None
    if prev_category != new_category:
        settings = get_settings()
        if not settings.discord_bot_token:
            raise HTTPException(
                status_code=503, detail="Discord bot token not configured."
            )
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            bot = DiscordBotClient(settings.discord_bot_token, http_client)
            try:
                parent_id = await resolve_feed_parent_id(bot, new_category)
            except FeedCategoryError as error:
                raise HTTPException(
                    status_code=400,
                    detail={"code": error.code, "message": error.message},
                ) from error
            try:
                moved = await move_feed_channels_to_category(
                    bot,
                    guild_id=guild_id,
                    config=previous,
                    parent_id=parent_id,
                )
            except DiscordBotAPIError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not move feed channels to category: {error}",
                ) from error
            logger.info(
                "Feed category changed guild=%s from=%s to=%s moved=%s",
                guild_id,
                prev_category,
                new_category,
                moved,
            )

    await save_config(
        guild_id, "feed_channels", payload, enabled=payload["enabled"]
    )
    await record_audit(
        session,
        entity_type="feed_config",
        action="update",
        guild_id=guild_id,
        changes={
            "enabled": {"from": previous.get("enabled"), "to": payload["enabled"]},
            "upvote_emoji": {
                "from": emoji_reaction_key(previous.get("upvote_emoji")),
                "to": emoji_reaction_key(payload.get("upvote_emoji")),
            },
            "downvote_emoji": {
                "from": emoji_reaction_key(previous.get("downvote_emoji")),
                "to": emoji_reaction_key(payload.get("downvote_emoji")),
            },
            "source_channel_ids": {
                "from": previous.get("source_channel_ids"),
                "to": payload.get("source_channel_ids"),
            },
            "excluded_channel_ids": {
                "from": previous.get("excluded_channel_ids"),
                "to": payload.get("excluded_channel_ids"),
            },
            "min_net_score": {
                "from": previous.get("min_net_score"),
                "to": payload.get("min_net_score"),
            },
            "display_limit": {
                "from": previous.get("display_limit"),
                "to": payload.get("display_limit"),
            },
            "refresh_interval_minutes": {
                "from": previous.get("refresh_interval_minutes"),
                "to": payload.get("refresh_interval_minutes"),
            },
            "feed_category_id": {
                "from": prev_category,
                "to": new_category,
            },
            "windows": {
                "from": previous.get("windows"),
                "to": payload.get("windows"),
            },
        },
    )
    await session.commit()
    merged = merge_feed_config(payload)
    return {
        "guild_id": guild_id,
        "config": merged,
        "next_refresh_at": compute_next_refresh_at(
            merged.get("last_full_sync_at"),
            merged.get("refresh_interval_minutes"),
        ),
    }


@router.patch("/guilds/{guild_id}/feed-channels/config")
async def patch_feed_enabled(
    body: FeedStateBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    config = await load_merged_feed_config(guild_id)
    config["enabled"] = body.enabled
    await save_config(guild_id, "feed_channels", config, enabled=body.enabled)
    await record_audit(
        session,
        entity_type="feed_config",
        action="enable" if body.enabled else "disable",
        guild_id=guild_id,
        changes={"enabled": body.enabled},
    )
    await session.commit()
    return {"guild_id": guild_id, "config": config}


@router.patch("/guilds/{guild_id}/feed-channels/windows/{window}")
async def patch_feed_window(
    body: FeedWindowPatchBody,
    guild_id: str = Path(pattern=SNOWFLAKE),
    window: FeedWindow = Path(),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    config = await load_merged_feed_config(guild_id)
    current = dict(config["windows"].get(window) or {})
    if body.enabled is not None:
        current["enabled"] = body.enabled
    if body.channel_id is not None:
        current["channel_id"] = body.channel_id
    if body.norgoth_managed is not None:
        current["norgoth_managed"] = body.norgoth_managed
    # Cleared channel → not configured.
    if body.channel_id == "" or (
        "channel_id" in body.model_fields_set and body.channel_id is None
    ):
        current["channel_id"] = None
        current["enabled"] = False
    config["windows"][window] = current
    await save_config(
        guild_id, "feed_channels", config, enabled=bool(config.get("enabled"))
    )
    await record_audit(
        session,
        entity_type="feed_window",
        action="update",
        guild_id=guild_id,
        entity_id=window,
        changes=current,
    )
    await session.commit()
    return {"guild_id": guild_id, "config": config}


@router.post("/guilds/{guild_id}/feed-channels/provision")
async def provision_feed_channels(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="Discord bot token not configured.")

    config = await load_merged_feed_config(guild_id)
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        bot = DiscordBotClient(settings.discord_bot_token, http_client)
        bot_user_id: str | None = None
        try:
            me = await bot.get_bot_user()
            bot_user_id = str(me.get("id") or "") or None
        except DiscordBotAPIError:
            pass
        overwrites = feed_channel_permission_overwrites(
            guild_id, bot_user_id=bot_user_id
        )
        try:
            parent_id = await resolve_feed_parent_id(
                bot, config.get("feed_category_id")
            )
        except FeedCategoryError as error:
            raise HTTPException(
                status_code=400,
                detail={"code": error.code, "message": error.message},
            ) from error
        for window in FEED_WINDOWS:
            window_cfg = config["windows"][window]
            if window_cfg.get("channel_id") or not window_cfg.get("norgoth_managed"):
                continue
            try:
                created = await bot.create_guild_channel(
                    guild_id,
                    name=f"feed-{window.replace('_', '-')}",
                    channel_type=CHANNEL_TYPE_TEXT,
                    parent_id=parent_id,
                    permission_overwrites=overwrites,
                    reason="Norgoth Feed Channels provision",
                )
                channel_id = str(created.get("id") or "") or None
                if channel_id:
                    window_cfg["channel_id"] = channel_id
                    window_cfg["enabled"] = True
                    results.append({"window": window, "status": "created"})
            except DiscordBotAPIError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not create feed channel for {window}: {error}",
                ) from error

    await save_config(
        guild_id, "feed_channels", config, enabled=bool(config.get("enabled"))
    )
    await record_audit(
        session,
        entity_type="feed_config",
        action="provision",
        guild_id=guild_id,
        changes={"results": results, "feed_category_id": config.get("feed_category_id")},
    )
    await session.commit()
    return {"guild_id": guild_id, "config": config, "results": results}


@router.post("/guilds/{guild_id}/feed-channels/repair")
async def repair_feed_channels_route(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Primary recovery: recreate missing channels and sync feed posts."""

    try:
        result = await repair_feed_channels(session, guild_id=guild_id)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Feed repair failed: {error}",
        ) from error
    # Always return a serializable body (never a false empty 500 after work).
    return result


@router.post("/guilds/{guild_id}/feed-channels/process-dirty")
async def process_feed_dirty(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Called by the bot dirty-drain loop."""

    results = await process_dirty_feeds(session, guild_id)
    return {"guild_id": guild_id, "results": results}


@router.get("/guilds/{guild_id}/feed-channels/status")
async def feed_status(
    guild_id: str = Path(pattern=SNOWFLAKE),
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    config = await load_merged_feed_config(guild_id)
    tracked = (
        await session.execute(
            select(func.count())
            .select_from(FeedMessage)
            .where(
                FeedMessage.guild_id == guild_id,
                FeedMessage.status == "active",
            )
        )
    ).scalar_one()
    votes_total = (
        await session.execute(
            select(func.count())
            .select_from(FeedVote)
            .where(FeedVote.guild_id == guild_id)
        )
    ).scalar_one()

    windows = []
    for key in FEED_WINDOWS:
        w = config["windows"][key]
        configured = bool(w.get("channel_id"))
        windows.append(
            {
                "key": key,
                "configured": configured,
                "enabled": bool(w.get("enabled") and configured),
                "channel_id": w.get("channel_id"),
                "last_updated": (config.get("last_refresh_at") or {}).get(key),
            }
        )

    warnings: list[str] = []
    if config.get("enabled"):
        if not config.get("source_channel_ids"):
            warnings.append("No source channels configured.")
        if emojis_equal(config.get("upvote_emoji"), config.get("downvote_emoji")):
            warnings.append("Upvote and downvote emojis must differ.")
        if not any(w["configured"] for w in windows):
            warnings.append("No feed destination channels configured.")

    top = (
        await session.execute(
            select(FeedMessage)
            .where(
                FeedMessage.guild_id == guild_id,
                FeedMessage.status == "active",
            )
            .order_by(
                FeedMessage.net_score.desc(),
                FeedMessage.upvote_count.desc(),
                FeedMessage.created_at.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "guild_id": guild_id,
        "enabled": bool(config.get("enabled")),
        "tracked_messages": int(tracked or 0),
        "votes_total": int(votes_total or 0),
        "windows": windows,
        "warnings": warnings,
        "top_message": (
            {
                "message_id": top.message_id,
                "net_score": top.net_score,
                "author_id": top.author_id,
            }
            if top
            else None
        ),
        "last_refresh_at": config.get("last_refresh_at") or {},
        "refresh_interval_minutes": clamp_refresh_interval_minutes(
            config.get("refresh_interval_minutes")
        ),
        "feed_category_id": config.get("feed_category_id"),
        "last_full_sync_at": config.get("last_full_sync_at"),
        "next_refresh_at": compute_next_refresh_at(
            config.get("last_full_sync_at"),
            config.get("refresh_interval_minutes"),
        ),
    }
