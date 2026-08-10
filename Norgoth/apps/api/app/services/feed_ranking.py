"""Feed Channels ranking windows, Redis keys, and score helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

FeedWindow = Literal["daily", "weekly", "monthly", "all_time"]
FEED_WINDOWS: tuple[FeedWindow, ...] = ("daily", "weekly", "monthly", "all_time")

DEFAULT_FEED_CONFIG: dict[str, Any] = {
    "enabled": False,
    "upvote_emoji": {
        "kind": "unicode",
        "id": None,
        "name": "👍",
        "animated": False,
        "reaction": "👍",
    },
    "downvote_emoji": {
        "kind": "unicode",
        "id": None,
        "name": "👎",
        "animated": False,
        "reaction": "👎",
    },
    "source_channel_ids": [],
    "excluded_channel_ids": [],
    "min_net_score": 1,
    "display_limit": 10,
    "refresh_interval_minutes": 15,
    "feed_category_id": None,
    "last_full_sync_at": None,
    "exclude_bots": True,
    "exclude_webhooks": True,
    "exclude_threads": True,
    "windows": {
        "daily": {"enabled": False, "channel_id": None, "norgoth_managed": False},
        "weekly": {"enabled": False, "channel_id": None, "norgoth_managed": False},
        "monthly": {"enabled": False, "channel_id": None, "norgoth_managed": False},
        "all_time": {"enabled": False, "channel_id": None, "norgoth_managed": False},
    },
    "last_refresh_at": {},
}

REFRESH_INTERVAL_MIN = 5
REFRESH_INTERVAL_MAX = 60
REFRESH_INTERVAL_STEP = 5
DISPLAY_LIMIT_MAX = 25


def clamp_refresh_interval_minutes(value: Any) -> int:
    """Normalize refresh interval to 5–60 in steps of 5."""

    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = int(DEFAULT_FEED_CONFIG["refresh_interval_minutes"])
    minutes = max(REFRESH_INTERVAL_MIN, min(REFRESH_INTERVAL_MAX, minutes))
    # Snap to nearest step of 5.
    snapped = (
        round((minutes - REFRESH_INTERVAL_MIN) / REFRESH_INTERVAL_STEP)
        * REFRESH_INTERVAL_STEP
        + REFRESH_INTERVAL_MIN
    )
    return max(REFRESH_INTERVAL_MIN, min(REFRESH_INTERVAL_MAX, int(snapped)))


def clamp_display_limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = int(DEFAULT_FEED_CONFIG["display_limit"])
    return max(1, min(DISPLAY_LIMIT_MAX, limit))


def parse_iso_utc(value: Any) -> datetime | None:
    """Parse an ISO timestamp into aware UTC datetime, or None."""

    if value is None:
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def now_iso_utc(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return current.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def touch_last_full_sync(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Set last_full_sync_at on config (mutates and returns)."""

    config["last_full_sync_at"] = now_iso_utc(now)
    return config


def compute_next_refresh_at(
    last_full_sync_at: Any,
    refresh_interval_minutes: Any,
    *,
    now: datetime | None = None,
) -> str:
    """Compute absolute next refresh ISO timestamp from PG scheduler state.

    If last sync is missing or next is already due/past, schedule from *now*
    plus the interval so the UI does not stick at 00:00:00.
    """

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    interval = clamp_refresh_interval_minutes(refresh_interval_minutes)
    last = parse_iso_utc(last_full_sync_at)
    if last is None:
        next_at = current + timedelta(minutes=interval)
    else:
        next_at = last + timedelta(minutes=interval)
        if next_at <= current:
            next_at = current + timedelta(minutes=interval)
    return next_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def feed_config_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:feed:config"


def feed_rank_key(guild_id: str, window: FeedWindow) -> str:
    return f"norgoth:guild:{guild_id}:feed:rank:{window}"


def feed_author_net_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:feed:author:net"


def feed_dirty_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:feed:dirty"


def feed_lock_key(guild_id: str, window: FeedWindow) -> str:
    return f"norgoth:guild:{guild_id}:feed:lock:{window}"


def feed_debounce_key(guild_id: str, window: FeedWindow) -> str:
    return f"norgoth:guild:{guild_id}:feed:debounce:{window}"


def window_bounds(
    window: FeedWindow,
    *,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Return inclusive-start / exclusive-end UTC bounds for a calendar window."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    if window == "all_time":
        return None, None

    if window == "daily":
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    if window == "weekly":
        # ISO week: Monday 00:00 UTC.
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        start = start - timedelta(days=start.weekday())
        return start, start + timedelta(days=7)

    # monthly — calendar month UTC
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def windows_for_timestamp(created_at: datetime) -> list[FeedWindow]:
    """Windows that currently include ``created_at`` (UTC calendar)."""

    now = datetime.now(timezone.utc)
    included: list[FeedWindow] = ["all_time"]
    for window in ("daily", "weekly", "monthly"):
        start, end = window_bounds(window, now=now)
        assert start is not None and end is not None
        ts = created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        if start <= ts < end:
            included.append(window)  # type: ignore[arg-type]
    return included


def composite_rank_score(
    net_score: int,
    upvote_count: int,
    created_at: datetime,
) -> float:
    """Encode tie-break into a single descending Redis ZSET score.

    Primary: net_score, then upvotes, then newer timestamp.
    """

    ts = created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    # Clamp components so the float stays well-ordered for practical ranges.
    net = max(min(int(net_score), 1_000_000), -1_000_000)
    ups = max(min(int(upvote_count), 1_000_000), 0)
    epoch = int(ts.timestamp())
    return float(net) * 1e15 + float(ups) * 1e9 + float(epoch)


def merge_feed_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Deep-merge stored config onto defaults."""

    base = {
        **DEFAULT_FEED_CONFIG,
        "windows": {
            key: dict(value)
            for key, value in DEFAULT_FEED_CONFIG["windows"].items()
        },
        "last_refresh_at": {},
    }
    if not raw:
        return base
    merged = {**base, **raw}
    windows = dict(base["windows"])
    for key, value in (raw.get("windows") or {}).items():
        if key in windows and isinstance(value, dict):
            windows[key] = {**windows[key], **value}
    merged["windows"] = windows
    merged["last_refresh_at"] = dict(raw.get("last_refresh_at") or {})
    merged["refresh_interval_minutes"] = clamp_refresh_interval_minutes(
        merged.get("refresh_interval_minutes")
    )
    merged["display_limit"] = clamp_display_limit(merged.get("display_limit"))
    cat = raw.get("feed_category_id")
    if cat is None or cat == "":
        merged["feed_category_id"] = None
    else:
        merged["feed_category_id"] = str(cat)
    last_sync = raw.get("last_full_sync_at")
    merged["last_full_sync_at"] = (
        str(last_sync) if last_sync not in (None, "") else None
    )
    return merged


async def load_merged_feed_config(guild_id: str) -> dict[str, Any]:
    """Read feed config via Redis/Postgres read-through and merge defaults."""

    from app.services.campaign_store import get_redis
    from app.services.feature_config_store import read_through

    redis_client = await get_redis()
    try:
        stored = await read_through(guild_id, "feed_channels", redis_client)
    finally:
        await redis_client.aclose()
    return merge_feed_config(stored if isinstance(stored, dict) else None)


def emoji_reaction_key(emoji: dict[str, Any] | None) -> str | None:
    if not emoji:
        return None
    reaction = emoji.get("reaction")
    if isinstance(reaction, str) and reaction:
        return reaction
    if emoji.get("kind") == "custom" and emoji.get("id"):
        name = emoji.get("name") or "emoji"
        prefix = "a" if emoji.get("animated") else ""
        return f"{prefix}:{name}:{emoji['id']}" if prefix else f"{name}:{emoji['id']}"
    name = emoji.get("name")
    return str(name) if name else None


def emojis_equal(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    return emoji_reaction_key(a) is not None and emoji_reaction_key(a) == emoji_reaction_key(
        b
    )
