"""Feed Channels ranking windows, Redis keys, and score helpers."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

FeedWindow = Literal["daily", "weekly", "monthly", "all_time"]
FEED_WINDOWS: tuple[FeedWindow, ...] = ("daily", "weekly", "monthly", "all_time")

DAILY_REFRESH_HOURS_MIN = 1
DAILY_REFRESH_HOURS_MAX = 12
# Shared Feed Refresh Interval default (applies to all windows).
DAILY_REFRESH_HOURS_DEFAULT = 4
FEED_REFRESH_HOURS_MIN = DAILY_REFRESH_HOURS_MIN
FEED_REFRESH_HOURS_MAX = DAILY_REFRESH_HOURS_MAX
FEED_REFRESH_HOURS_DEFAULT = DAILY_REFRESH_HOURS_DEFAULT

# Legacy guild-level minute clamp (pre per-window schedules).
REFRESH_INTERVAL_MIN = 5
REFRESH_INTERVAL_MAX = 60
REFRESH_INTERVAL_STEP = 5
DISPLAY_LIMIT_MAX = 25
FEED_REFRESH_LOCK_TTL_SEC = 600
FEED_REFRESH_RETRY_CAP_MINUTES = 5


def _default_window(window: FeedWindow) -> dict[str, Any]:
    _ = window
    return {
        "enabled": False,
        "channel_id": None,
        "norgoth_managed": False,
        "schedule_anchor_at": None,
        "next_refresh_at": None,
        "last_refresh_at": None,
        "refresh_interval_hours": DAILY_REFRESH_HOURS_DEFAULT,
    }


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
    "refresh_interval_minutes": DAILY_REFRESH_HOURS_DEFAULT * 60,
    "daily_refresh_interval_hours": DAILY_REFRESH_HOURS_DEFAULT,
    "feed_category_id": None,
    "last_full_sync_at": None,
    "next_refresh_at": None,
    "exclude_bots": True,
    "exclude_webhooks": True,
    "exclude_threads": True,
    "windows": {window: _default_window(window) for window in FEED_WINDOWS},
    "last_refresh_at": {},
}


def clamp_refresh_interval_minutes(value: Any) -> int:
    """Normalize legacy refresh interval to 5–60 in steps of 5."""

    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = int(DEFAULT_FEED_CONFIG["refresh_interval_minutes"])
    minutes = max(REFRESH_INTERVAL_MIN, min(REFRESH_INTERVAL_MAX, minutes))
    snapped = (
        round((minutes - REFRESH_INTERVAL_MIN) / REFRESH_INTERVAL_STEP)
        * REFRESH_INTERVAL_STEP
        + REFRESH_INTERVAL_MIN
    )
    return max(REFRESH_INTERVAL_MIN, min(REFRESH_INTERVAL_MAX, int(snapped)))


def clamp_daily_refresh_interval_hours(value: Any) -> int:
    """Normalize shared feed refresh interval to 1–12 hours.

    Invalid or missing values fall back to the 4-hour default. Values already
    inside 1–12 are preserved (legacy Daily configs keep their setting).
    """

    try:
        hours = int(value)
    except (TypeError, ValueError):
        hours = FEED_REFRESH_HOURS_DEFAULT
    return max(FEED_REFRESH_HOURS_MIN, min(FEED_REFRESH_HOURS_MAX, hours))


# Prefer the shared name in new call sites; keep the daily alias for imports.
clamp_feed_refresh_interval_hours = clamp_daily_refresh_interval_hours


def legacy_minutes_to_daily_hours(minutes: Any) -> int:
    """Map legacy guild minutes onto daily hours (5–60 → 1h floor)."""

    try:
        raw = int(minutes)
    except (TypeError, ValueError):
        return DAILY_REFRESH_HOURS_DEFAULT
    return clamp_daily_refresh_interval_hours(round(raw / 60))


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


def _aware_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def add_calendar_months(dt: datetime, months: int) -> datetime:
    """Add calendar months, clamping day to the last day of the target month."""

    current = _aware_utc(dt)
    month_index = current.month - 1 + int(months)
    year = current.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(current.day, last_day)
    return current.replace(year=year, month=month, day=day)


def window_cadence_label(
    window: FeedWindow,
    *,
    hours: int | None = None,
) -> str:
    """Shared refresh cadence label for every feed period."""

    _ = window
    value = (
        clamp_daily_refresh_interval_hours(hours)
        if hours is not None
        else FEED_REFRESH_HOURS_DEFAULT
    )
    unit = "hour" if value == 1 else "hours"
    return f"Every {value} {unit}"


def first_occurrence_after_anchor(
    window: FeedWindow,
    anchor: datetime,
    *,
    daily_hours: int = FEED_REFRESH_HOURS_DEFAULT,
) -> datetime:
    """First scheduled occurrence after the anchor (one shared interval later)."""

    _ = window
    start = _aware_utc(anchor)
    hours = clamp_daily_refresh_interval_hours(daily_hours)
    return start + timedelta(hours=hours)


def next_occurrence_after(
    window: FeedWindow,
    anchor: datetime,
    after: datetime,
    *,
    daily_hours: int = FEED_REFRESH_HOURS_DEFAULT,
) -> datetime:
    """Least occurrence on the shared hourly grid that is strictly after ``after``."""

    _ = window
    start = _aware_utc(anchor)
    cutoff = _aware_utc(after)
    period = timedelta(hours=clamp_daily_refresh_interval_hours(daily_hours))
    period_seconds = period.total_seconds()
    if period_seconds <= 0:
        raise ValueError("invalid cadence period")

    delta = (cutoff - start).total_seconds()
    if delta < 0:
        return start + period
    n = int(delta // period_seconds) + 1
    if n < 1:
        n = 1
    return start + timedelta(seconds=n * period_seconds)


def daily_hours_from_config(config: dict[str, Any]) -> int:
    windows = config.get("windows") or {}
    daily = windows.get("daily") if isinstance(windows, dict) else None
    if isinstance(daily, dict) and daily.get("refresh_interval_hours") is not None:
        return clamp_daily_refresh_interval_hours(daily.get("refresh_interval_hours"))
    if config.get("daily_refresh_interval_hours") is not None:
        return clamp_daily_refresh_interval_hours(
            config.get("daily_refresh_interval_hours")
        )
    if config.get("refresh_interval_minutes") is not None:
        return legacy_minutes_to_daily_hours(config.get("refresh_interval_minutes"))
    return DAILY_REFRESH_HOURS_DEFAULT


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
    stored_next_refresh_at: Any = None,
) -> str | None:
    """Legacy next Discord full-sync time (guild-level minute interval)."""

    _ = now
    stored = parse_iso_utc(stored_next_refresh_at)
    if stored is not None:
        return stored.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    last = parse_iso_utc(last_full_sync_at)
    if last is None:
        return None
    interval = clamp_refresh_interval_minutes(refresh_interval_minutes)
    next_at = last + timedelta(minutes=interval)
    return next_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_next_refresh_at(config: dict[str, Any]) -> str | None:
    """Earliest enabled window next_refresh_at, else legacy guild schedule."""

    windows = config.get("windows") or {}
    earliest: datetime | None = None
    for key in FEED_WINDOWS:
        wcfg = windows.get(key) if isinstance(windows, dict) else None
        if not isinstance(wcfg, dict) or not wcfg.get("enabled"):
            continue
        nxt = parse_iso_utc(wcfg.get("next_refresh_at"))
        if nxt is None:
            continue
        if earliest is None or nxt < earliest:
            earliest = nxt
    if earliest is not None:
        return earliest.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return compute_next_refresh_at(
        config.get("last_full_sync_at"),
        config.get("refresh_interval_minutes"),
        stored_next_refresh_at=config.get("next_refresh_at"),
    )


def _sync_guild_schedule_mirrors(config: dict[str, Any]) -> dict[str, Any]:
    """Mirror daily hours and earliest window schedule onto guild-level fields."""

    hours = daily_hours_from_config(config)
    config["daily_refresh_interval_hours"] = hours
    config["refresh_interval_minutes"] = hours * 60

    windows = config.get("windows") or {}
    if isinstance(windows, dict):
        daily = windows.get("daily")
        if isinstance(daily, dict):
            daily["refresh_interval_hours"] = hours

    resolved = resolve_next_refresh_at(config)
    if resolved is not None:
        config["next_refresh_at"] = resolved

    latest: datetime | None = None
    last_map = dict(config.get("last_refresh_at") or {})
    for key in FEED_WINDOWS:
        wcfg = windows.get(key) if isinstance(windows, dict) else None
        if not isinstance(wcfg, dict):
            continue
        last = parse_iso_utc(wcfg.get("last_refresh_at"))
        if last is not None:
            last_map[key] = wcfg["last_refresh_at"]
            if latest is None or last > latest:
                latest = last
    config["last_refresh_at"] = last_map
    if latest is not None:
        config["last_full_sync_at"] = now_iso_utc(latest)
    return config


def window_countdown_fields(
    config: dict[str, Any],
    window: FeedWindow,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Countdown payload for a single ranking window."""

    current = _aware_utc(now)
    windows = config.get("windows") or {}
    wcfg = windows.get(window) if isinstance(windows, dict) else None
    if not isinstance(wcfg, dict):
        wcfg = {}
    hours = daily_hours_from_config(config) if window == "daily" else None
    next_at = wcfg.get("next_refresh_at")
    last = wcfg.get("last_refresh_at")
    remaining: int | None = None
    if next_at is not None:
        next_dt = parse_iso_utc(next_at)
        if next_dt is not None:
            remaining = max(0, int((next_dt - current).total_seconds()))
    if next_at:
        status = "due" if remaining == 0 else "scheduled"
    elif wcfg.get("enabled") and is_window_refresh_due(config, window, now=current):
        status = "due"
    else:
        status = "pending"
    shared_hours = daily_hours_from_config(config)
    return {
        "window": window,
        "enabled": bool(wcfg.get("enabled")),
        "schedule_anchor_at": wcfg.get("schedule_anchor_at"),
        "last_refresh_at": last,
        "next_refresh_at": next_at,
        "remaining_seconds": remaining,
        "scheduler_status": status,
        "cadence_label": window_cadence_label(window, hours=shared_hours),
        "refresh_interval_hours": shared_hours,
    }


def is_window_refresh_due(
    config: dict[str, Any],
    window: FeedWindow,
    *,
    now: datetime | None = None,
) -> bool:
    """True when an enabled window should rebuild."""

    if not config.get("enabled"):
        return False
    windows = config.get("windows") or {}
    wcfg = windows.get(window) if isinstance(windows, dict) else None
    if not isinstance(wcfg, dict) or not wcfg.get("enabled"):
        return False
    current = _aware_utc(now)
    next_at = parse_iso_utc(wcfg.get("next_refresh_at"))
    if next_at is not None:
        return current >= next_at
    anchor = parse_iso_utc(wcfg.get("schedule_anchor_at"))
    if anchor is None:
        return True
    hours = daily_hours_from_config(config)
    first = first_occurrence_after_anchor(window, anchor, daily_hours=hours)
    return current >= first


def due_feed_windows(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[FeedWindow]:
    return [window for window in FEED_WINDOWS if is_window_refresh_due(config, window, now=now)]


def is_feed_refresh_due(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """True when any enabled window is due for refresh."""

    return bool(due_feed_windows(config, now=now))


def scheduler_countdown_fields(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Canonical countdown payload for API consumers (guild + per-window)."""

    current = _aware_utc(now)
    hours = daily_hours_from_config(config)
    interval_minutes = hours * 60
    last = config.get("last_full_sync_at")
    next_at = resolve_next_refresh_at(config)
    remaining: int | None = None
    if next_at is not None:
        next_dt = parse_iso_utc(next_at)
        if next_dt is not None:
            remaining = max(0, int((next_dt - current).total_seconds()))
    if next_at:
        status = "due" if remaining == 0 else "scheduled"
    elif is_feed_refresh_due(config, now=current):
        status = "due"
    else:
        status = "pending"
    return {
        "refresh_interval_minutes": interval_minutes,
        "daily_refresh_interval_hours": hours,
        "last_full_sync_at": last,
        "last_refresh_at": last,
        "next_refresh_at": next_at,
        "server_time": now_iso_utc(current),
        "remaining_seconds": remaining,
        "scheduler_status": status,
        "windows": {
            window: window_countdown_fields(config, window, now=current)
            for window in FEED_WINDOWS
        },
    }


def ensure_window_schedule(
    config: dict[str, Any],
    window: FeedWindow,
    *,
    now: datetime | None = None,
    reset_anchor: bool = False,
) -> dict[str, Any]:
    """Ensure a window has schedule_anchor_at and next_refresh_at."""

    current = _aware_utc(now)
    windows = config.setdefault("windows", {})
    if not isinstance(windows, dict):
        windows = {}
        config["windows"] = windows
    existing = windows.get(window)
    wcfg = (
        {**_default_window(window), **existing}
        if isinstance(existing, dict)
        else _default_window(window)
    )
    windows[window] = wcfg
    hours = daily_hours_from_config(config)
    wcfg["refresh_interval_hours"] = hours

    anchor = None if reset_anchor else parse_iso_utc(wcfg.get("schedule_anchor_at"))
    if anchor is None:
        last_map = config.get("last_refresh_at") or {}
        anchor = (
            parse_iso_utc(wcfg.get("last_refresh_at"))
            or parse_iso_utc(
                last_map.get(window) if isinstance(last_map, dict) else None
            )
            or parse_iso_utc(config.get("last_full_sync_at"))
            or current
        )
        wcfg["schedule_anchor_at"] = now_iso_utc(anchor)

    if reset_anchor or parse_iso_utc(wcfg.get("next_refresh_at")) is None:
        nxt = next_occurrence_after(window, anchor, current, daily_hours=hours)
        wcfg["next_refresh_at"] = now_iso_utc(nxt)

    return _sync_guild_schedule_mirrors(config)


def schedule_window_after_success(
    config: dict[str, Any],
    window: FeedWindow,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark a successful window rebuild and advance its cadence."""

    current = _aware_utc(now)
    windows = config.setdefault("windows", {})
    if not isinstance(windows, dict):
        windows = {}
        config["windows"] = windows
    existing = windows.get(window)
    wcfg = (
        {**_default_window(window), **existing}
        if isinstance(existing, dict)
        else _default_window(window)
    )
    windows[window] = wcfg
    hours = daily_hours_from_config(config)
    wcfg["refresh_interval_hours"] = hours

    if parse_iso_utc(wcfg.get("schedule_anchor_at")) is None:
        wcfg["schedule_anchor_at"] = now_iso_utc(current)
    anchor = parse_iso_utc(wcfg["schedule_anchor_at"])
    assert anchor is not None

    wcfg["last_refresh_at"] = now_iso_utc(current)
    wcfg["next_refresh_at"] = now_iso_utc(
        next_occurrence_after(window, anchor, current, daily_hours=hours)
    )

    last_map = dict(config.get("last_refresh_at") or {})
    last_map[window] = wcfg["last_refresh_at"]
    config["last_refresh_at"] = last_map
    return _sync_guild_schedule_mirrors(config)


def schedule_window_after_failure(
    config: dict[str, Any],
    window: FeedWindow,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Do not advance last refresh; set a short retry next_refresh_at."""

    current = _aware_utc(now)
    windows = config.setdefault("windows", {})
    if not isinstance(windows, dict):
        windows = {}
        config["windows"] = windows
    existing = windows.get(window)
    wcfg = (
        {**_default_window(window), **existing}
        if isinstance(existing, dict)
        else _default_window(window)
    )
    windows[window] = wcfg

    hours = daily_hours_from_config(config)
    interval_minutes = hours * 60
    backoff = min(interval_minutes, FEED_REFRESH_RETRY_CAP_MINUTES)
    wcfg["next_refresh_at"] = now_iso_utc(current + timedelta(minutes=backoff))
    return _sync_guild_schedule_mirrors(config)


def schedule_after_daily_interval_change(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Keep each window anchor; recompute next_refresh_at on the shared hourly grid."""

    current = _aware_utc(now)
    windows = config.setdefault("windows", {})
    if not isinstance(windows, dict):
        windows = {}
        config["windows"] = windows

    hours = daily_hours_from_config(config)
    for window in FEED_WINDOWS:
        existing = windows.get(window)
        wcfg = (
            {**_default_window(window), **existing}
            if isinstance(existing, dict)
            else _default_window(window)
        )
        windows[window] = wcfg
        wcfg["refresh_interval_hours"] = hours

        anchor = parse_iso_utc(wcfg.get("schedule_anchor_at"))
        if anchor is None:
            anchor = current
            wcfg["schedule_anchor_at"] = now_iso_utc(anchor)

        nxt = next_occurrence_after(
            window,
            anchor,
            current - timedelta(microseconds=1),
            daily_hours=hours,
        )
        wcfg["next_refresh_at"] = now_iso_utc(nxt)

    return _sync_guild_schedule_mirrors(config)


def schedule_after_success(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark successful sync and advance all enabled window schedules."""

    current = _aware_utc(now)
    touch_last_full_sync(config, now=current)
    windows = config.get("windows") or {}
    any_enabled = False
    for window in FEED_WINDOWS:
        wcfg = windows.get(window) if isinstance(windows, dict) else None
        if isinstance(wcfg, dict) and wcfg.get("enabled"):
            any_enabled = True
            schedule_window_after_success(config, window, now=current)
    if not any_enabled:
        hours = daily_hours_from_config(config)
        config["next_refresh_at"] = now_iso_utc(
            current + timedelta(minutes=hours * 60)
        )
        config["daily_refresh_interval_hours"] = hours
        config["refresh_interval_minutes"] = hours * 60
        return config
    return _sync_guild_schedule_mirrors(config)


def schedule_after_interval_change(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Legacy helper: maps to daily interval reschedule."""

    return schedule_after_daily_interval_change(config, now=now)


def schedule_after_failure(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Do not advance last sync; set retry backoff on enabled windows."""

    current = _aware_utc(now)
    windows = config.get("windows") or {}
    any_enabled = False
    for window in FEED_WINDOWS:
        wcfg = windows.get(window) if isinstance(windows, dict) else None
        if isinstance(wcfg, dict) and wcfg.get("enabled"):
            any_enabled = True
            schedule_window_after_failure(config, window, now=current)
    if not any_enabled:
        hours = daily_hours_from_config(config)
        backoff = min(hours * 60, FEED_REFRESH_RETRY_CAP_MINUTES)
        config["next_refresh_at"] = now_iso_utc(
            current + timedelta(minutes=backoff)
        )
        return config
    return _sync_guild_schedule_mirrors(config)


def ensure_persisted_next_refresh(config: dict[str, Any]) -> bool:
    """Backfill missing window/guild next_refresh_at. Returns whether dirty."""

    dirty = False
    windows = config.setdefault("windows", {})
    if not isinstance(windows, dict):
        windows = {}
        config["windows"] = windows

    for window in FEED_WINDOWS:
        existing = windows.get(window)
        if not isinstance(existing, dict):
            continue
        before_next = existing.get("next_refresh_at")
        before_anchor = existing.get("schedule_anchor_at")
        ensure_window_schedule(config, window)
        wcfg = windows.get(window) or {}
        if wcfg.get("next_refresh_at") != before_next or wcfg.get(
            "schedule_anchor_at"
        ) != before_anchor:
            dirty = True

    if parse_iso_utc(config.get("next_refresh_at")) is None:
        resolved = resolve_next_refresh_at(config)
        if resolved:
            config["next_refresh_at"] = resolved
            dirty = True
        elif parse_iso_utc(config.get("last_full_sync_at")) is not None:
            derived = compute_next_refresh_at(
                config.get("last_full_sync_at"),
                config.get("refresh_interval_minutes"),
            )
            if derived:
                config["next_refresh_at"] = derived
                dirty = True
    return dirty


def backfill_window_schedules(
    config: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Ensure every window has schedule fields; migrate legacy guild interval."""

    current = _aware_utc(now)
    hours = daily_hours_from_config(config)
    windows_raw = config.get("windows") or {}
    windows: dict[str, Any] = dict(windows_raw) if isinstance(windows_raw, dict) else {}
    last_map = dict(config.get("last_refresh_at") or {})

    for window in FEED_WINDOWS:
        base = _default_window(window)
        existing = windows.get(window)
        wcfg = {**base, **existing} if isinstance(existing, dict) else dict(base)
        windows[window] = wcfg

        if wcfg.get("refresh_interval_hours") is None:
            wcfg["refresh_interval_hours"] = hours
        else:
            wcfg["refresh_interval_hours"] = clamp_daily_refresh_interval_hours(
                wcfg.get("refresh_interval_hours")
            )
        if window == "daily":
            hours = clamp_daily_refresh_interval_hours(wcfg["refresh_interval_hours"])
            # Keep other windows aligned to the shared guild interval.
            for other in FEED_WINDOWS:
                if other == "daily":
                    continue
                other_cfg = windows.get(other)
                if isinstance(other_cfg, dict):
                    other_cfg["refresh_interval_hours"] = hours

        if parse_iso_utc(wcfg.get("schedule_anchor_at")) is None:
            anchor = (
                parse_iso_utc(wcfg.get("last_refresh_at"))
                or parse_iso_utc(last_map.get(window))
                or parse_iso_utc(config.get("last_full_sync_at"))
                or current
            )
            wcfg["schedule_anchor_at"] = now_iso_utc(anchor)

        if parse_iso_utc(wcfg.get("next_refresh_at")) is None:
            guild_next = parse_iso_utc(config.get("next_refresh_at"))
            anchor = parse_iso_utc(wcfg["schedule_anchor_at"])
            assert anchor is not None
            if guild_next is not None and window == "daily":
                wcfg["next_refresh_at"] = now_iso_utc(guild_next)
            else:
                wcfg["next_refresh_at"] = now_iso_utc(
                    next_occurrence_after(
                        window,
                        anchor,
                        current - timedelta(microseconds=1),
                        daily_hours=hours,
                    )
                )

        if wcfg.get("last_refresh_at"):
            last_map[window] = wcfg["last_refresh_at"]

    config["windows"] = windows
    config["last_refresh_at"] = last_map
    config["daily_refresh_interval_hours"] = hours
    config["refresh_interval_minutes"] = hours * 60
    return _sync_guild_schedule_mirrors(config)


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


def feed_refresh_lock_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:feed:refresh-lock"


def feed_debounce_key(guild_id: str, window: FeedWindow) -> str:
    return f"norgoth:guild:{guild_id}:feed:debounce:{window}"


def window_bounds(
    window: FeedWindow,
    *,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Return inclusive UTC eligibility bounds for a feed period.

    Period controls ranking eligibility, not refresh cadence:

    - daily: rolling previous 24 hours ``[T-24h, T]``
    - weekly: rolling previous 7 days ``[T-7d, T]``
    - monthly: rolling previous calendar month ``[add_calendar_months(T,-1), T]``
    - all_time: no age cutoff
    """

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    if window == "all_time":
        return None, None

    if window == "daily":
        return current - timedelta(hours=24), current

    if window == "weekly":
        return current - timedelta(days=7), current

    # monthly — one calendar month lookback via add_calendar_months
    return add_calendar_months(current, -1), current


def windows_for_timestamp(
    created_at: datetime,
    *,
    now: datetime | None = None,
) -> list[FeedWindow]:
    """Windows whose rolling eligibility currently includes ``created_at``."""

    current = now or datetime.now(timezone.utc)
    included: list[FeedWindow] = ["all_time"]
    for window in ("daily", "weekly", "monthly"):
        start, end = window_bounds(window, now=current)
        assert start is not None and end is not None
        ts = created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        if start <= ts <= end:
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
    """Deep-merge stored config onto defaults; backfill per-window schedules."""

    base = {
        **DEFAULT_FEED_CONFIG,
        "windows": {
            key: dict(value)
            for key, value in DEFAULT_FEED_CONFIG["windows"].items()
        },
        "last_refresh_at": {},
    }
    if not raw:
        return backfill_window_schedules(base)

    merged = {**base, **raw}
    windows = dict(base["windows"])
    for key, value in (raw.get("windows") or {}).items():
        if key in windows and isinstance(value, dict):
            windows[key] = {**windows[key], **value}
    merged["windows"] = windows
    merged["last_refresh_at"] = dict(raw.get("last_refresh_at") or {})
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
    next_refresh = raw.get("next_refresh_at")
    merged["next_refresh_at"] = (
        str(next_refresh) if next_refresh not in (None, "") else None
    )

    daily = merged["windows"].setdefault("daily", _default_window("daily"))
    raw_windows = raw.get("windows") if isinstance(raw.get("windows"), dict) else {}
    raw_daily = raw_windows.get("daily") if isinstance(raw_windows, dict) else None
    if isinstance(raw_daily, dict) and raw_daily.get("refresh_interval_hours") is not None:
        daily["refresh_interval_hours"] = clamp_daily_refresh_interval_hours(
            raw_daily.get("refresh_interval_hours")
        )
    elif raw.get("daily_refresh_interval_hours") is not None:
        daily["refresh_interval_hours"] = clamp_daily_refresh_interval_hours(
            raw.get("daily_refresh_interval_hours")
        )
    elif raw.get("refresh_interval_minutes") is not None:
        daily["refresh_interval_hours"] = legacy_minutes_to_daily_hours(
            raw.get("refresh_interval_minutes")
        )

    hours = clamp_daily_refresh_interval_hours(daily.get("refresh_interval_hours"))
    daily["refresh_interval_hours"] = hours
    for key in FEED_WINDOWS:
        wcfg = merged["windows"].setdefault(key, _default_window(key))
        wcfg["refresh_interval_hours"] = hours
    merged["daily_refresh_interval_hours"] = hours
    merged["refresh_interval_minutes"] = hours * 60

    return backfill_window_schedules(merged)


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
