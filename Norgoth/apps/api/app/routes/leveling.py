"""Leveling configuration and leaderboard."""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.db.session import get_session_factory
from app.models.runtime_events import MemberXp
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

router = APIRouter(
    tags=["Leveling"],
    dependencies=[Depends(guild_manager_dependency())],
)

SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"


def leveling_config_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:leveling:config"


def xp_key(guild_id: str) -> str:
    """Total XP ZSET (text + voice); used for levels /rank."""

    return f"norgoth:guild:{guild_id}:xp"


def xp_text_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:xp:text"


def xp_voice_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:xp:voice"


def guild_members_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:members"


XpMetric = Literal["text", "voice", "net_upvotes"]


LEVEL_THRESHOLD_SCALE_MIN = 0.5
LEVEL_THRESHOLD_SCALE_MAX = 2.0
DEFAULT_LEVEL_THRESHOLD_SCALE = 1.0


def clamp_threshold_scale(scale: float) -> float:
    """Clamp the curve scale into the supported range (fail-safe to default)."""

    try:
        value = float(scale)
    except (TypeError, ValueError):
        return DEFAULT_LEVEL_THRESHOLD_SCALE
    return max(LEVEL_THRESHOLD_SCALE_MIN, min(LEVEL_THRESHOLD_SCALE_MAX, value))


def xp_for_level(level: int, scale: float = DEFAULT_LEVEL_THRESHOLD_SCALE) -> int:
    """Total XP required to reach ``level`` (cumulative MEE6-style curve).

    ``scale`` stretches (>1) or compresses (<1) the whole curve so admins can
    tune how quickly level requirements grow. Stored XP is never rewritten, so
    changing the scale re-derives everyone's level live.
    """

    scale = clamp_threshold_scale(scale)
    total = 0
    for step in range(level):
        total += 5 * step**2 + 50 * step + 100
    return int(round(total * scale))


def level_from_xp(xp: int, scale: float = DEFAULT_LEVEL_THRESHOLD_SCALE) -> int:
    scale = clamp_threshold_scale(scale)
    level = 0
    while xp >= xp_for_level(level + 1, scale):
        level += 1
    return level


class RewardRole(BaseModel):
    level: int = Field(ge=1, le=1000)
    role_id: str = Field(pattern=SNOWFLAKE_PATTERN)


class LevelingConfig(BaseModel):
    announce_mode: Literal["current", "channel", "off"] = "current"
    announce_channel_id: Optional[str] = Field(
        default=None, pattern=SNOWFLAKE_PATTERN
    )
    # Base XP awarded per eligible message (before the multiplier). Bounded to
    # keep progression balanced and prevent runaway values.
    xp_per_message: int = Field(default=15, ge=1, le=100)
    # Reward magnitude multiplier. Scales the base XP only; it does NOT relax
    # the cooldown / anti-spam eligibility gate enforced by the bot.
    xp_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    # Stretches (>1) or compresses (<1) the level-up XP curve. Levels are always
    # derived live from stored XP, so changing this never rewrites XP — it only
    # changes how much XP each level requires.
    level_threshold_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    # Level-up messages are always delivered as an embed. This body is the
    # single source of truth for the embed description.
    level_up_message: str = Field(
        default="🎉 {user} reached level **{level}**!",
        max_length=2000,
    )
    level_up_embed: dict[str, Any] = Field(default_factory=dict)
    reward_roles: list[RewardRole] = Field(default_factory=list, max_length=25)
    # Voice Chat XP. The bot awards `voice_xp_per_minute` XP per minute of
    # eligible voice participation (see the bot's voice-XP loop for the
    # eligibility policy). A value of 0 disables voice XP entirely — there is no
    # separate enable flag; the numeric value is the source of truth. The global
    # `xp_multiplier` scales this the same way it scales message XP.
    voice_xp_per_minute: int = Field(default=0, ge=0, le=100)


@router.get("/guilds/{guild_id}/leveling/config")
async def get_leveling_config(guild_id: str) -> dict[str, Any]:
    redis_client = await get_redis()

    try:
        raw = await read_raw(guild_id, "leveling", redis_client)
    finally:
        await redis_client.aclose()

    defaults = LevelingConfig().model_dump()

    if not raw:
        return defaults

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return defaults

    if not isinstance(stored, dict):
        return defaults

    merged = {**defaults, **{k: v for k, v in stored.items() if k in defaults}}

    # Legacy migration: older configs gated voice XP with a boolean
    # `voice_xp_enabled`. When that flag was explicitly off, coerce the
    # per-minute value to 0 (the new disabled state). The boolean itself is not
    # part of the schema anymore, so it is dropped from the response.
    if stored.get("voice_xp_enabled") is False:
        merged["voice_xp_per_minute"] = 0

    return merged


@router.put("/guilds/{guild_id}/leveling/config")
async def update_leveling_config(
    guild_id: str,
    config: LevelingConfig,
) -> dict[str, Any]:
    payload = config.model_dump()
    payload["updated_at"] = now_iso()

    redis_client = await get_redis()

    try:
        await save_config(guild_id, "leveling", payload)
    finally:
        await redis_client.aclose()

    return payload


@router.get("/guilds/{guild_id}/leveling/leaderboard")
async def get_leaderboard(
    guild_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    metric: XpMetric = Query(default="text"),
) -> list[dict[str, Any]]:
    if metric == "net_upvotes":
        return await _get_net_upvote_leaderboard(guild_id, limit)

    redis_client = await get_redis()
    metric_key = xp_text_key(guild_id) if metric == "text" else xp_voice_key(guild_id)
    xp_column = MemberXp.text_xp if metric == "text" else MemberXp.voice_xp

    try:
        entries = await redis_client.zrevrange(
            metric_key,
            0,
            limit - 1,
            withscores=True,
        )
        raw_members = await redis_client.get(guild_members_key(guild_id))
        raw_config = await read_raw(guild_id, "leveling", redis_client)

        # Redis ZSET is a hot cache. When empty, rebuild from Postgres, then
        # (for text) heal from legacy total ``:xp`` when PG has no text rows.
        if not entries:
            factory = get_session_factory()
            try:
                async with factory() as session:
                    rows = (
                        await session.execute(
                            select(MemberXp)
                            .where(MemberXp.guild_id == guild_id)
                            .order_by(xp_column.desc())
                            .limit(limit)
                        )
                    ).scalars().all()
            except ProgrammingError as error:
                # Schema lag (e.g. missing text_xp/voice_xp) — not an empty board.
                raise HTTPException(
                    status_code=503,
                    detail="Database schema out of date; run alembic upgrade head",
                ) from error
            entries = [
                (
                    row.user_id,
                    float(row.text_xp if metric == "text" else row.voice_xp),
                )
                for row in rows
                if (row.text_xp if metric == "text" else row.voice_xp) > 0
            ]
            if entries:
                pipe = redis_client.pipeline()
                for user_id, score in entries:
                    pipe.zadd(metric_key, {str(user_id): score})
                for row in rows:
                    if row.xp > 0:
                        pipe.zadd(xp_key(guild_id), {str(row.user_id): float(row.xp)})
                    # Keep the sibling metric ZSET warm from PG when present.
                    if row.text_xp > 0:
                        pipe.zadd(
                            xp_text_key(guild_id), {str(row.user_id): float(row.text_xp)}
                        )
                    if row.voice_xp > 0:
                        pipe.zadd(
                            xp_voice_key(guild_id),
                            {str(row.user_id): float(row.voice_xp)},
                        )
                await pipe.execute()
            elif metric == "text":
                # Pre-split totals lived only on ``:xp``. Attribute to text,
                # warm the text ZSET, and upsert durable Postgres rows.
                legacy = await redis_client.zrevrange(
                    xp_key(guild_id),
                    0,
                    limit - 1,
                    withscores=True,
                )
                if legacy:
                    entries = [
                        (str(user_id), float(score))
                        for user_id, score in legacy
                        if float(score) > 0
                    ]
                    if entries:
                        pipe = redis_client.pipeline()
                        for user_id, score in entries:
                            pipe.zadd(xp_text_key(guild_id), {str(user_id): score})
                        await pipe.execute()

                        async with factory() as session:
                            for user_id, score in entries:
                                xp_int = int(score)
                                row = (
                                    await session.execute(
                                        select(MemberXp)
                                        .where(
                                            MemberXp.guild_id == guild_id,
                                            MemberXp.user_id == str(user_id),
                                        )
                                        .with_for_update()
                                    )
                                ).scalar_one_or_none()
                                if row is None:
                                    session.add(
                                        MemberXp(
                                            guild_id=guild_id,
                                            user_id=str(user_id),
                                            xp=xp_int,
                                            text_xp=xp_int,
                                            voice_xp=0,
                                        )
                                    )
                                elif row.text_xp <= 0:
                                    row.text_xp = xp_int
                                    row.xp = max(row.xp, xp_int + row.voice_xp)
                            await session.commit()
    finally:
        await redis_client.aclose()

    # Levels are derived live from stored XP using the guild's curve scale.
    scale = DEFAULT_LEVEL_THRESHOLD_SCALE
    if raw_config:
        try:
            parsed_config = json.loads(raw_config)
            if isinstance(parsed_config, dict):
                scale = clamp_threshold_scale(
                    parsed_config.get(
                        "level_threshold_scale", DEFAULT_LEVEL_THRESHOLD_SCALE
                    )
                )
        except json.JSONDecodeError:
            pass

    # Resolve display name + avatar from the bot's member snapshot without
    # any per-user Discord API calls (avoids N+1). Discord User ID stays the
    # authoritative identifier; the snapshot is a best-effort presentation
    # cache. Name resolution prefers the Discord-wide identity:
    # global display name -> username -> guild display name -> shortened ID.
    names: dict[str, str] = {}
    usernames: dict[str, str] = {}
    avatars: dict[str, str | None] = {}

    if raw_members:
        try:
            snapshot = json.loads(raw_members)
            for member in snapshot.get("members", []):
                member_id = str(member.get("id"))
                resolved_name = (
                    member.get("global_name")
                    or member.get("name")
                    or member.get("display_name")
                )
                if resolved_name:
                    names[member_id] = str(resolved_name)
                username = member.get("name")
                if username:
                    usernames[member_id] = str(username)
                avatar_url = member.get("avatar_url")
                if avatar_url:
                    avatars[member_id] = str(avatar_url)
        except (json.JSONDecodeError, AttributeError):
            pass

    def short_id(user_id: str) -> str:
        return f"User {user_id[-4:]}" if len(user_id) >= 4 else f"User {user_id}"

    leaderboard: list[dict[str, Any]] = []

    for index, (user_id, score) in enumerate(entries, start=1):
        xp = int(score)
        user_id_str = str(user_id)
        leaderboard.append(
            {
                "rank": index,
                "user_id": user_id_str,
                "name": names.get(user_id_str) or short_id(user_id_str),
                "username": usernames.get(user_id_str),
                "avatar_url": avatars.get(user_id_str),
                "xp": xp,
                "level": level_from_xp(xp, scale),
            }
        )

    return leaderboard


async def _get_net_upvote_leaderboard(
    guild_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    """All-Time Top Net Upvote — PG ``feed_author_stats`` with Redis ZSET cache."""

    from app.models.feed_channels import FeedAuthorStats
    from app.services.feed_ranking import feed_author_net_key

    redis_client = await get_redis()
    try:
        metric_key = feed_author_net_key(guild_id)
        entries = await redis_client.zrevrange(
            metric_key, 0, limit - 1, withscores=True
        )
        raw_members = await redis_client.get(guild_members_key(guild_id))

        stats_by_user: dict[str, FeedAuthorStats] = {}
        if not entries:
            factory = get_session_factory()
            async with factory() as session:
                rows = (
                    await session.execute(
                        select(FeedAuthorStats)
                        .where(FeedAuthorStats.guild_id == guild_id)
                        .order_by(FeedAuthorStats.net_score.desc())
                        .limit(limit)
                    )
                ).scalars().all()
            entries = [
                (row.user_id, float(row.net_score))
                for row in rows
                if int(row.net_score) != 0 or int(row.post_count) > 0
            ]
            stats_by_user = {row.user_id: row for row in rows}
            if entries:
                pipe = redis_client.pipeline()
                for user_id, score in entries:
                    pipe.zadd(metric_key, {str(user_id): score})
                await pipe.execute()
        else:
            factory = get_session_factory()
            user_ids = [str(uid) for uid, _ in entries]
            async with factory() as session:
                rows = (
                    await session.execute(
                        select(FeedAuthorStats).where(
                            FeedAuthorStats.guild_id == guild_id,
                            FeedAuthorStats.user_id.in_(user_ids),
                        )
                    )
                ).scalars().all()
            stats_by_user = {row.user_id: row for row in rows}
    finally:
        await redis_client.aclose()

    names: dict[str, str] = {}
    usernames: dict[str, str] = {}
    avatars: dict[str, str | None] = {}
    if raw_members:
        try:
            snapshot = json.loads(raw_members)
            for member in snapshot.get("members", []):
                member_id = str(member.get("id"))
                resolved_name = (
                    member.get("global_name")
                    or member.get("name")
                    or member.get("display_name")
                )
                if resolved_name:
                    names[member_id] = str(resolved_name)
                username = member.get("name")
                if username:
                    usernames[member_id] = str(username)
                avatar_url = member.get("avatar_url")
                if avatar_url:
                    avatars[member_id] = str(avatar_url)
        except (json.JSONDecodeError, AttributeError):
            pass

    def short_id(user_id: str) -> str:
        return f"User {user_id[-4:]}" if len(user_id) >= 4 else f"User {user_id}"

    leaderboard: list[dict[str, Any]] = []
    for index, (user_id, score) in enumerate(entries, start=1):
        user_id_str = str(user_id)
        stats = stats_by_user.get(user_id_str)
        leaderboard.append(
            {
                "rank": index,
                "user_id": user_id_str,
                "name": names.get(user_id_str) or short_id(user_id_str),
                "username": usernames.get(user_id_str),
                "avatar_url": avatars.get(user_id_str),
                "xp": int(score),
                "level": 0,
                "net_upvotes": int(stats.net_score) if stats else int(score),
                "upvote_total": int(stats.upvote_total) if stats else 0,
                "downvote_total": int(stats.downvote_total) if stats else 0,
                "post_count": int(stats.post_count) if stats else 0,
            }
        )
    return leaderboard
