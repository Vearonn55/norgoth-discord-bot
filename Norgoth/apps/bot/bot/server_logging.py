"""Server event logging: member, message, role, and channel events.

Each event is appended to a Redis ring buffer (norgoth:guild:{id}:eventlog)
for the dashboard and, when a log channel is configured, posted as an embed.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import discord
import httpx
from discord.ext import commands

from bot.audit_detail import (
    AuditDetail,
    build_channel_update_detail,
    build_role_update_detail,
    build_thread_update_detail,
    discord_embed_field_changes,
)
from bot.logging_presentation import compose_log_embed_spec
from bot.permission_diff import (
    channel_overwrite_fields,
    diff_channel_overwrite_items,
    diff_channel_overwrites,
    diff_role_permissions,
    role_permission_fields,
)
from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.serverlog")

EVENT_LOG_CAP = 1000

CATEGORY_COLORS = {
    "member": discord.Color.green(),
    "message": discord.Color.blurple(),
    "role": discord.Color.gold(),
    "channel": discord.Color.teal(),
    "server": discord.Color.purple(),
    "voice": discord.Color.teal(),
    "thread": discord.Color.dark_teal(),
    "moderation": discord.Color.red(),
    "security": discord.Color.dark_red(),
    "tickets": discord.Color.blurple(),
    "invites": discord.Color.green(),
    "verification": discord.Color.green(),
}

# Categories that should warn loudly when unrouted / undeliverable.
_ROUTE_WARN_CATEGORIES = frozenset({"tickets", "invites", "verification"})

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "log_channel_id": None,
    "member_events": True,
    "message_events": True,
    "role_events": True,
    "channel_events": True,
    "member_channel_id": None,
    "message_channel_id": None,
    "role_channel_id": None,
    "channel_channel_id": None,
    "groups": [],
}


def logging_config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:logging"


def routing_snapshot_key(guild_id: int | str) -> str:
    """Postgres-backed, denormalised routing map written by the API."""

    return f"norgoth:guild:{guild_id}:logging:routing"


def event_log_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:eventlog"


ACTOR_MISSING_PERMISSION = (
    "Unavailable — NorBot is missing View Audit Log permission"
)
ACTOR_UNAVAILABLE = "Unavailable — Discord audit entry not available"
ACTOR_SYSTEM = "System/Integration action"
ACTOR_NORBOT = "Executed by NorBot"
_AUDIT_FORBIDDEN_LOG_INTERVAL_S = 3600.0
_AUDIT_RETRY_AFTER_CAP_S = 2.0

_OVERWRITE_ACTIONS = frozenset(
    {
        discord.AuditLogAction.overwrite_create,
        discord.AuditLogAction.overwrite_update,
        discord.AuditLogAction.overwrite_delete,
    }
)


def actor_fallback_text(status: str) -> str:
    if status == "missing_permission":
        return ACTOR_MISSING_PERMISSION
    return ACTOR_UNAVAILABLE


def format_audit_actor_name(
    user: Any,
    *,
    reason: str | None,
    bot_user_id: int | None,
) -> str:
    if user is None:
        return ACTOR_SYSTEM
    reason_text = reason or ""
    user_id = getattr(user, "id", None)
    if (
        bot_user_id is not None
        and user_id == bot_user_id
        and reason_text.startswith("NorBot")
    ):
        return ACTOR_NORBOT
    name = str(user)
    if getattr(user, "bot", False) is True:
        return f"{name} (bot)"
    return name


def _http_retry_after_seconds(error: BaseException) -> float:
    retry_after = getattr(error, "retry_after", None)
    if retry_after is not None:
        try:
            return min(max(float(retry_after), 0.0), _AUDIT_RETRY_AFTER_CAP_S)
        except (TypeError, ValueError):
            pass
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) if response is not None else None
    if headers is not None:
        raw = None
        try:
            raw = headers.get("Retry-After") or headers.get("retry-after")
        except Exception:  # noqa: BLE001
            raw = None
        if raw is not None:
            try:
                return min(max(float(raw), 0.0), _AUDIT_RETRY_AFTER_CAP_S)
            except (TypeError, ValueError):
                pass
    return 1.0


def _entry_extra_id(entry: Any) -> int | None:
    extra = getattr(entry, "extra", None)
    extra_id = getattr(extra, "id", None) if extra is not None else None
    if extra_id is None:
        return None
    try:
        return int(extra_id)
    except (TypeError, ValueError):
        return None


def _entry_target_id(entry: Any) -> int | None:
    target = getattr(entry, "target", None)
    target_id = getattr(target, "id", None) if target is not None else None
    if target_id is None:
        return None
    try:
        return int(target_id)
    except (TypeError, ValueError):
        return None


def build_log_embed(
    title: str,
    description: str,
    *,
    color: discord.Color,
    fields: dict[str, str] | None = None,
    footer: str | None = None,
    event_type: str | None = None,
) -> discord.Embed:
    """Standardised log embed used for every routed logging event."""

    spec = compose_log_embed_spec(
        title,
        description,
        fields=fields,
        footer=footer,
        event_type=event_type,
    )
    embed = discord.Embed(
        title=spec["title"],
        description=spec["description"] or None,
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    if spec["footer"]:
        embed.set_footer(text=spec["footer"])
    for name, value, inline in spec["fields"]:
        embed.add_field(name=name, value=value, inline=inline)
    return embed


class ServerLoggingCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        self._audit_rate_limited_until: dict[int, float] = {}
        self._audit_forbidden_logged_at: dict[int, float] = {}
        self._enrich_tasks: set[asyncio.Task[Any]] = set()

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(logging_config_key(guild_id))
        return {**DEFAULT_CONFIG, **stored}

    async def get_routing_snapshot(self, guild_id: int) -> dict[str, Any] | None:
        """Read the API-managed routing snapshot, if one exists and is active."""

        snapshot = await self.bot.state.get_json(routing_snapshot_key(guild_id))
        if snapshot and snapshot.get("enabled") and snapshot.get("events"):
            return snapshot
        return None

    async def route_event(
        self,
        guild: discord.Guild,
        event_type: str,
        category: str,
        title: str,
        description: str,
        fields: dict[str, str],
        *,
        actor_name: str | None = None,
    ) -> list[tuple[str, str]]:
        """Send a standardised embed to the channel/colour resolved for an event.

        Prefers the API-managed routing snapshot (event_type -> channel + colour).
        Falls back to the legacy Redis logging config when no snapshot matches.
        Returns ``(channel_id, message_id)`` pairs for messages that were sent.
        """

        channel_ids: set[str] = set()
        color: discord.Color = CATEGORY_COLORS.get(
            category, discord.Color.dark_grey()
        )

        snapshot = await self.get_routing_snapshot(guild.id)
        routed = snapshot["events"].get(event_type) if snapshot else None
        if routed and routed.get("channel_id"):
            channel_ids.add(str(routed["channel_id"]))
            if routed.get("color") is not None:
                try:
                    color = discord.Color(int(routed["color"]))
                except (ValueError, TypeError):
                    pass
        else:
            channel_ids = self._legacy_channel_ids(
                await self.get_config(guild.id), category, event_type
            )

        if not channel_ids:
            logger.warning(
                "log delivery failed class=unmapped guild_id=%s event_type=%s "
                "category=%s channel_id=none",
                guild.id,
                event_type,
                category,
            )
            return []

        footer = f"NorBot · {category} event"
        if actor_name:
            footer = f"{footer} · by {actor_name}"
        embed = build_log_embed(
            title,
            description,
            color=color,
            fields=fields,
            footer=footer,
            event_type=event_type,
        )

        allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
        posted: list[tuple[str, str]] = []
        for channel_id in channel_ids:
            channel = await self._resolve_text_channel(
                guild, channel_id, event_type=event_type
            )
            if channel is None:
                continue
            try:
                message = await channel.send(embed=embed, allowed_mentions=allowed)
                posted.append((str(channel.id), str(message.id)))
            except discord.Forbidden as error:
                logger.warning(
                    "log delivery failed class=forbidden guild_id=%s "
                    "event_type=%s channel_id=%s discord_status=%s discord_code=%s",
                    guild.id,
                    event_type,
                    channel_id,
                    getattr(error, "status", None),
                    getattr(error, "code", None),
                )
            except discord.HTTPException as error:
                logger.warning(
                    "log delivery failed class=http guild_id=%s "
                    "event_type=%s channel_id=%s discord_status=%s discord_code=%s",
                    guild.id,
                    event_type,
                    channel_id,
                    getattr(error, "status", None),
                    getattr(error, "code", None),
                )
        if not posted and category in _ROUTE_WARN_CATEGORIES:
            logger.warning(
                "log delivery failed class=undelivered guild_id=%s "
                "event_type=%s channel_ids=%s",
                guild.id,
                event_type,
                sorted(channel_ids),
            )
        return posted

    async def _resolve_text_channel(
        self,
        guild: discord.Guild,
        channel_id: str,
        *,
        event_type: str,
    ) -> discord.TextChannel | None:
        """Resolve a text channel by ID, fetching once on cache miss."""

        channel: discord.abc.GuildChannel | discord.Thread | None
        try:
            cid = int(channel_id)
        except (TypeError, ValueError):
            logger.warning(
                "log delivery failed class=missing_channel guild_id=%s "
                "event_type=%s channel_id=%s reason=invalid_id",
                guild.id,
                event_type,
                channel_id,
            )
            return None

        channel = guild.get_channel(cid)
        if channel is None:
            try:
                fetched = await guild.fetch_channel(cid)
            except discord.NotFound:
                logger.warning(
                    "log delivery failed class=missing_channel guild_id=%s "
                    "event_type=%s channel_id=%s reason=not_found",
                    guild.id,
                    event_type,
                    channel_id,
                )
                return None
            except discord.Forbidden:
                logger.warning(
                    "log delivery failed class=forbidden guild_id=%s "
                    "event_type=%s channel_id=%s reason=fetch_forbidden",
                    guild.id,
                    event_type,
                    channel_id,
                )
                return None
            except discord.HTTPException as error:
                logger.warning(
                    "log delivery failed class=http guild_id=%s "
                    "event_type=%s channel_id=%s reason=fetch "
                    "discord_status=%s discord_code=%s",
                    guild.id,
                    event_type,
                    channel_id,
                    getattr(error, "status", None),
                    getattr(error, "code", None),
                )
                return None
            channel = fetched

        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "log delivery failed class=missing_channel guild_id=%s "
                "event_type=%s channel_id=%s reason=not_text_channel type=%s",
                guild.id,
                event_type,
                channel_id,
                type(channel).__name__,
            )
            return None
        return channel

    def _legacy_channel_ids(
        self,
        config: dict[str, Any],
        category: str,
        event_type: str,
    ) -> set[str]:
        """Resolve target channels from the legacy Redis config."""

        if not config.get("enabled", True):
            return set()
        if not config.get(f"{category}_events", True):
            return set()

        channel_ids: set[str] = set()
        for group in config.get("groups") or []:
            if not isinstance(group, dict) or not group.get("enabled", True):
                continue
            keys = group.get("event_keys") or []
            if event_type in keys:
                gid = group.get("channel_id")
                if gid:
                    channel_ids.add(str(gid))

        fallback = config.get(f"{category}_channel_id") or config.get(
            "log_channel_id"
        )
        if fallback and not channel_ids:
            channel_ids.add(str(fallback))
        return channel_ids

    async def log_moderation(
        self,
        guild: discord.Guild,
        event_type: str,
        title: str,
        description: str,
        fields: dict[str, str],
        *,
        actor_name: str | None = None,
    ) -> None:
        """Route a moderation action through config-driven logging.

        Moderation actions keep their own audit trail (moderation log); this only
        mirrors them into a configured logging channel when routing is set up.
        """

        if not await self.bot.state.is_module_enabled(guild.id, "logging"):
            return
        try:
            await self.route_event(
                guild,
                event_type,
                "moderation",
                title,
                description,
                fields,
                actor_name=actor_name,
            )
        except Exception:  # noqa: BLE001 - logging must never break moderation
            logger.exception("Failed to route moderation log event")

    async def resolve_audit_actor(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        *,
        target_id: int | None = None,
        actions: Sequence[discord.AuditLogAction] | None = None,
        since: datetime | None = None,
        max_wait_s: float = 0.0,
    ) -> tuple[str | None, str | None]:
        """Best-effort actor lookup from Discord's audit log."""

        actor_id, actor_name, _status, _reason = await self._resolve_audit_actor_detailed(
            guild,
            action,
            target_id=target_id,
            actions=actions,
            since=since,
            max_wait_s=max_wait_s,
        )
        return actor_id, actor_name

    async def _resolve_audit_actor_detailed(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        *,
        target_id: int | None = None,
        actions: Sequence[discord.AuditLogAction] | None = None,
        since: datetime | None = None,
        max_wait_s: float = 0.0,
        retry_delays: Sequence[float] | None = None,
        overwrite_target_ids: set[int] | None = None,
    ) -> tuple[str | None, str | None, str, str | None]:
        """Return (actor_id, actor_name, status, reason).

        status is found, delayed, ambiguous, missing_permission, rate_limited,
        or unavailable. Unique actor ID is required when a time window is set.
        """

        action_set = tuple(dict.fromkeys(actions if actions else (action,)))
        if retry_delays is None:
            delays: list[float] = [0.0]
            if max_wait_s > 0:
                delays.append(max_wait_s)
        else:
            delays = list(retry_delays)[:3]

        last_error: str | None = None
        delayed = False
        for index, delay in enumerate(delays):
            if delay > 0:
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    raise
                delayed = True
            matches, error = await self._collect_audit_actor_matches(
                guild,
                action_set,
                target_id=target_id,
                since=since,
                overwrite_target_ids=overwrite_target_ids,
            )
            if error == "missing_permission":
                return None, None, "missing_permission", None
            if error:
                last_error = error
                continue
            if matches:
                return self._finish_audit_actor_matches(matches, delayed=delayed)
            last_error = None
            _ = index
        return None, None, last_error or "unavailable", None

    def _finish_audit_actor_matches(
        self,
        matches: list[tuple[str | None, str, str | None, bool]],
        *,
        delayed: bool,
    ) -> tuple[str | None, str | None, str, str | None]:
        preferred = [item for item in matches if item[3]] or list(matches)
        unique: dict[str, str] = {}
        reasons: dict[str, str | None] = {}
        for actor_id, actor_name, reason, _signature in preferred:
            key = actor_id or ""
            unique.setdefault(key, actor_name)
            if key not in reasons or not reasons[key]:
                reasons[key] = reason
        if len(unique) != 1:
            return None, None, "ambiguous", None
        actor_key, actor_name = next(iter(unique.items()))
        status = "delayed" if delayed else "found"
        actor_id = actor_key or None
        return actor_id, actor_name, status, reasons.get(actor_key)

    def _audit_entry_matches(
        self,
        entry: Any,
        *,
        target_id: int | None,
        overwrite_target_ids: set[int] | None,
        since: datetime | None,
    ) -> bool:
        if since is not None:
            created = getattr(entry, "created_at", None)
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created < since:
                    return False

        action = getattr(entry, "action", None)
        entry_target = _entry_target_id(entry)
        extra_id = _entry_extra_id(entry)
        if action in _OVERWRITE_ACTIONS:
            extra_ok = (
                extra_id is None
                or not overwrite_target_ids
                or extra_id in overwrite_target_ids
            )
            target_ok = (
                target_id is None
                or entry_target is None
                or entry_target == target_id
            )
            if overwrite_target_ids and extra_id in overwrite_target_ids:
                return target_ok
            return extra_ok and target_ok
        if target_id is not None and entry_target is not None:
            return entry_target == target_id
        return True

    def _log_missing_audit_permission(self, guild_id: int) -> None:
        now = time.monotonic()
        last = self._audit_forbidden_logged_at.get(guild_id, 0.0)
        if now - last < _AUDIT_FORBIDDEN_LOG_INTERVAL_S:
            return
        self._audit_forbidden_logged_at[guild_id] = now
        logger.warning(
            "channel_actor_status=missing_permission guild_id=%s",
            guild_id,
        )

    async def _collect_audit_actor_matches(
        self,
        guild: discord.Guild,
        actions: Sequence[discord.AuditLogAction],
        *,
        target_id: int | None,
        since: datetime | None,
        overwrite_target_ids: set[int] | None = None,
        _retried_429: bool = False,
    ) -> tuple[list[tuple[str | None, str, str | None, bool]] | None, str | None]:
        """Return (matches, error). Empty matches means a successful miss."""

        cooldown_until = self._audit_rate_limited_until.get(guild.id, 0.0)
        if time.monotonic() < cooldown_until:
            return None, "rate_limited"

        bot_user_id = getattr(getattr(guild, "me", None), "id", None)
        matches: list[tuple[str | None, str, str | None, bool]] = []
        queried: list[discord.AuditLogAction] = []
        for action in actions:
            if action in queried:
                continue
            if len(queried) >= 3:
                break
            queried.append(action)
            try:
                async for entry in guild.audit_logs(limit=6, action=action):
                    if entry.action != action:
                        continue
                    if not self._audit_entry_matches(
                        entry,
                        target_id=target_id,
                        overwrite_target_ids=overwrite_target_ids,
                        since=since,
                    ):
                        continue
                    raw_reason = getattr(entry, "reason", None)
                    reason = (
                        str(raw_reason).strip()[:512]
                        if isinstance(raw_reason, str) and raw_reason.strip()
                        else None
                    )
                    user = entry.user
                    extra_id = _entry_extra_id(entry)
                    signature = bool(
                        action in _OVERWRITE_ACTIONS
                        and overwrite_target_ids
                        and extra_id in overwrite_target_ids
                    )
                    if user is None:
                        matches.append((None, ACTOR_SYSTEM, reason, signature))
                        continue
                    matches.append(
                        (
                            str(user.id),
                            format_audit_actor_name(
                                user,
                                reason=reason,
                                bot_user_id=bot_user_id,
                            ),
                            reason,
                            signature,
                        )
                    )
            except discord.Forbidden:
                self._log_missing_audit_permission(guild.id)
                return None, "missing_permission"
            except discord.HTTPException as error:
                status = getattr(error, "status", None)
                if status == 429:
                    delay = _http_retry_after_seconds(error)
                    self._audit_rate_limited_until[guild.id] = (
                        time.monotonic() + delay
                    )
                    if not _retried_429:
                        try:
                            await asyncio.sleep(delay)
                        except asyncio.CancelledError:
                            raise
                        return await self._collect_audit_actor_matches(
                            guild,
                            actions,
                            target_id=target_id,
                            since=since,
                            overwrite_target_ids=overwrite_target_ids,
                            _retried_429=True,
                        )
                    logger.warning(
                        "channel_actor_status=rate_limited guild_id=%s "
                        "discord_status=%s discord_code=%s",
                        guild.id,
                        status,
                        getattr(error, "code", None),
                    )
                    return None, "rate_limited"
                logger.warning(
                    "audit actor lookup failed guild_id=%s discord_status=%s "
                    "discord_code=%s",
                    guild.id,
                    status,
                    getattr(error, "code", None),
                )
                return None, "unavailable"
        return matches, None

    async def record_event(
        self,
        guild: discord.Guild,
        category: str,
        action: str,
        description: str,
        fields: dict[str, str] | None = None,
        *,
        event_type: str,
        actor_id: str | None = None,
        actor_name: str | None = None,
        detail: AuditDetail | dict[str, Any] | None = None,
        target_discord_user_id: str | None = None,
        target_username: str | None = None,
        target_display_name: str | None = None,
    ) -> dict[str, Any]:
        if not await self.bot.state.is_module_enabled(guild.id, "logging"):
            return {"id": None, "posted": [], "fields": dict(fields or {})}

        entry_fields = dict(fields or {})
        if actor_name and "Actor" not in entry_fields:
            entry_fields["Actor"] = actor_name
        if actor_id and "Actor ID" not in entry_fields:
            entry_fields["Actor ID"] = actor_id

        # Redis remains the Discord-log / fast ring cache. Durable details go
        # to Postgres via ingest.
        entry = {
            "id": str(uuid.uuid4()),
            "category": category,
            "action": action,
            "description": description,
            "fields": entry_fields,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "event_type": event_type,
            "created_at": now_iso(),
            "target_discord_user_id": target_discord_user_id,
            "target_username": target_username,
            "target_display_name": target_display_name,
        }

        try:
            await self.bot.state.append_capped_list(
                event_log_key(guild.id),
                entry,
                cap=EVENT_LOG_CAP,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to append event log entry")

        try:
            await self._ingest_server_event(guild.id, entry, detail)
        except Exception:  # noqa: BLE001
            logger.debug(
                "Server event ingest failed guild_id=%s event_type=%s",
                guild.id,
                event_type,
                exc_info=True,
            )

        posted: list[tuple[str, str]] = []
        try:
            posted = await self.route_event(
                guild,
                event_type,
                category,
                action,
                description,
                entry_fields,
                actor_name=actor_name,
            )
        except Exception:  # noqa: BLE001 - routing must not break event capture
            logger.exception("Failed to route log event %s", event_type)

        if posted:
            channel_id, message_id = posted[0]
            try:
                await self._patch_server_event(
                    guild.id,
                    str(entry["id"]),
                    {
                        "discord_channel_id": channel_id,
                        "discord_message_id": message_id,
                    },
                )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Server event message-id patch failed guild_id=%s event_type=%s",
                    guild.id,
                    event_type,
                    exc_info=True,
                )

        return {
            "id": entry["id"],
            "posted": posted,
            "fields": entry_fields,
            "action": action,
            "description": description,
            "event_type": event_type,
            "category": category,
        }

    async def _ingest_server_event(
        self,
        guild_id: int,
        entry: dict[str, Any],
        detail: AuditDetail | dict[str, Any] | None,
    ) -> None:
        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if not isinstance(base, str) or not base:
            return
        if not isinstance(token, str) or not token:
            return

        detail_payload: dict[str, Any] | None
        if isinstance(detail, AuditDetail):
            detail_payload = None if detail.is_empty() else detail.to_dict()
        elif isinstance(detail, dict):
            detail_payload = detail
        else:
            detail_payload = None

        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{base}/internal/ingest/{guild_id}/server-event",
                headers={
                    "X-Norgoth-Internal-Token": token,
                    "X-Norgoth-Bot-Token": token,
                },
                json={
                    "event_type": entry.get("event_type"),
                    "source_event_id": entry.get("id"),
                    "category": entry.get("category"),
                    "action": entry.get("action"),
                    "actor_id": entry.get("actor_id"),
                    "actor_name": entry.get("actor_name"),
                    "created_at": entry.get("created_at"),
                    "payload": {
                        "description": entry.get("description"),
                        "fields": entry.get("fields") or {},
                        "detail": detail_payload,
                        "target_discord_user_id": entry.get("target_discord_user_id"),
                        "username": entry.get("target_username"),
                        "display_name": entry.get("target_display_name"),
                    },
                },
            )

    async def _patch_server_event(
        self,
        guild_id: int,
        source_event_id: str,
        body: dict[str, Any],
    ) -> None:
        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if not isinstance(base, str) or not base:
            return
        if not isinstance(token, str) or not token:
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(
                f"{base}/internal/ingest/{guild_id}/server-event/{source_event_id}",
                headers={
                    "X-Norgoth-Internal-Token": token,
                    "X-Norgoth-Bot-Token": token,
                },
                json=body,
            )

    async def _rewrite_event_log_actor(
        self,
        guild_id: int,
        source_event_id: str,
        *,
        actor_id: str | None,
        actor_name: str,
    ) -> None:
        try:
            await self.bot.state.update_list_entry_by_id(
                event_log_key(guild_id),
                source_event_id,
                {
                    "actor_id": actor_id,
                    "actor_name": actor_name,
                    "fields": {"Actor": actor_name, **(
                        {"Actor ID": actor_id} if actor_id else {}
                    )},
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Event log actor rewrite failed guild_id=%s source_event_id=%s",
                guild_id,
                source_event_id,
                exc_info=True,
            )

    async def _edit_routed_log_messages(
        self,
        guild: discord.Guild,
        posted: list[tuple[str, str]],
        *,
        event_type: str,
        category: str,
        title: str,
        description: str,
        fields: dict[str, str],
        actor_name: str | None,
    ) -> None:
        color = CATEGORY_COLORS.get(category, discord.Color.dark_grey())
        snapshot = await self.get_routing_snapshot(guild.id)
        routed = snapshot["events"].get(event_type) if snapshot else None
        if routed and routed.get("color") is not None:
            try:
                color = discord.Color(int(routed["color"]))
            except (ValueError, TypeError):
                pass
        footer = f"NorBot · {category} event"
        if actor_name:
            footer = f"{footer} · by {actor_name}"
        embed = build_log_embed(
            title,
            description,
            color=color,
            fields=fields,
            footer=footer,
            event_type=event_type,
        )
        for channel_id, message_id in posted:
            channel = await self._resolve_text_channel(
                guild, channel_id, event_type=event_type
            )
            if channel is None:
                continue
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=embed)
            except (discord.HTTPException, ValueError, TypeError):
                logger.debug(
                    "Late actor embed edit failed guild_id=%s channel_id=%s "
                    "message_id=%s",
                    guild.id,
                    channel_id,
                    message_id,
                    exc_info=True,
                )

    def _schedule_channel_actor_enrichment(
        self,
        *,
        guild: discord.Guild,
        source_event_id: str | None,
        posted: list[tuple[str, str]],
        actions: Sequence[discord.AuditLogAction],
        target_id: int,
        overwrite_target_ids: set[int],
        event_type: str,
        category: str,
        title: str,
        description: str,
        fields: dict[str, str],
        detail: AuditDetail,
    ) -> None:
        if not source_event_id or not posted:
            return
        task = asyncio.create_task(
            self._enrich_channel_update_actor(
                guild,
                source_event_id=source_event_id,
                posted=posted,
                actions=actions,
                target_id=target_id,
                overwrite_target_ids=overwrite_target_ids,
                event_type=event_type,
                category=category,
                title=title,
                description=description,
                fields=dict(fields),
                detail=detail,
            )
        )
        self._enrich_tasks.add(task)
        task.add_done_callback(self._enrich_tasks.discard)

    async def _enrich_channel_update_actor(
        self,
        guild: discord.Guild,
        *,
        source_event_id: str,
        posted: list[tuple[str, str]],
        actions: Sequence[discord.AuditLogAction],
        target_id: int,
        overwrite_target_ids: set[int],
        event_type: str,
        category: str,
        title: str,
        description: str,
        fields: dict[str, str],
        detail: AuditDetail,
    ) -> None:
        try:
            await asyncio.sleep(1.2)
            since = datetime.now(timezone.utc) - timedelta(seconds=8)
            actor_id, actor_name, status, reason = (
                await self._resolve_audit_actor_detailed(
                    guild,
                    actions[0],
                    target_id=target_id,
                    actions=actions,
                    since=since,
                    retry_delays=(0.0,),
                    overwrite_target_ids=overwrite_target_ids or None,
                )
            )
            if status not in {"found", "delayed"} or not actor_name:
                logger.info(
                    "channel_actor_status=%s guild_id=%s event_type=%s",
                    status,
                    guild.id,
                    event_type,
                )
                return
            fields["Actor"] = actor_name
            if actor_id:
                fields["Actor ID"] = actor_id
            detail.actor = {"id": actor_id, "name": actor_name}
            detail.reason = reason
            await self._rewrite_event_log_actor(
                guild.id,
                source_event_id,
                actor_id=actor_id,
                actor_name=actor_name,
            )
            await self._patch_server_event(
                guild.id,
                source_event_id,
                {
                    "actor_id": actor_id,
                    "actor_name": actor_name,
                    "actor_field": actor_name,
                    "detail_actor": detail.actor,
                },
            )
            await self._edit_routed_log_messages(
                guild,
                posted,
                event_type=event_type,
                category=category,
                title=title,
                description=description,
                fields=fields,
                actor_name=actor_name,
            )
            logger.info(
                "channel_actor_status=enriched guild_id=%s event_type=%s",
                guild.id,
                event_type,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.debug(
                "channel actor enrichment failed guild_id=%s source_event_id=%s",
                guild.id,
                source_event_id,
                exc_info=True,
            )

    # ---- member events -------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.record_event(
            member.guild,
            "member",
            "Member joined",
            f"{member.display_name} ({member}) joined the server.",
            {
                "Member": f"{member} ({member.id})",
                "Account created": member.created_at.strftime("%Y-%m-%d"),
                "Member count": str(member.guild.member_count),
            },
            event_type="member_join",
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        roles = [role.name for role in member.roles if not role.is_default()]
        actor_id, actor_name = await self.resolve_audit_actor(
            member.guild,
            discord.AuditLogAction.kick,
            target_id=member.id,
        )

        if actor_name:
            await self.record_event(
                member.guild,
                "member",
                "Member kicked",
                f"{member} ({member.id}) was kicked by {actor_name}.",
                {
                    "Member": f"{member} ({member.id})",
                    "Roles": ", ".join(roles) if roles else "None",
                    "Member count": str(member.guild.member_count),
                },
                event_type="member_kick",
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return

        await self.record_event(
            member.guild,
            "member",
            "Member left",
            f"{member} ({member.id}) left the server.",
            {
                "Member": f"{member} ({member.id})",
                "Roles": ", ".join(roles) if roles else "None",
                "Member count": str(member.guild.member_count),
            },
            event_type="member_leave",
        )

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        before_timeout = getattr(before, "timed_out_until", None)
        after_timeout = getattr(after, "timed_out_until", None)
        if before_timeout != after_timeout and after_timeout is not None:
            actor_id, actor_name = await self.resolve_audit_actor(
                after.guild,
                discord.AuditLogAction.member_update,
                target_id=after.id,
            )
            await self.record_event(
                after.guild,
                "member",
                "Member timed out",
                f"{after.display_name} was timed out.",
                {
                    "Member": f"{after} ({after.id})",
                    "Until": after_timeout.strftime("%Y-%m-%d %H:%M UTC"),
                },
                event_type="member_timeout",
                actor_id=actor_id,
                actor_name=actor_name,
            )
        elif before_timeout is not None and after_timeout is None:
            actor_id, actor_name = await self.resolve_audit_actor(
                after.guild,
                discord.AuditLogAction.member_update,
                target_id=after.id,
            )
            await self.record_event(
                after.guild,
                "member",
                "Timeout cleared",
                f"{after.display_name}'s timeout was cleared.",
                {"Member": f"{after} ({after.id})"},
                event_type="member_timeout_clear",
                actor_id=actor_id,
                actor_name=actor_name,
            )

        if before.nick != after.nick:
            actor_id, actor_name = await self.resolve_audit_actor(
                after.guild,
                discord.AuditLogAction.member_update,
                target_id=after.id,
            )
            await self.record_event(
                after.guild,
                "member",
                "Nickname changed",
                (
                    f"{after.display_name}'s nickname changed from "
                    f"“{before.nick or before.name}” to "
                    f"“{after.nick or after.name}”."
                ),
                {
                    "Member": f"{after} ({after.id})",
                    "Before": before.nick or before.name,
                    "After": after.nick or after.name,
                },
                event_type="member_nickname",
                actor_id=actor_id,
                actor_name=actor_name,
            )

        if before.roles != after.roles:
            gained = [r for r in after.roles if r not in before.roles]
            lost = [r for r in before.roles if r not in after.roles]

            if gained or lost:
                changes = {"Member": f"{after} ({after.id})"}
                if gained:
                    changes["Added"] = ", ".join(role.name for role in gained)
                if lost:
                    changes["Removed"] = ", ".join(role.name for role in lost)

                actor_id, actor_name = await self.resolve_audit_actor(
                    after.guild,
                    discord.AuditLogAction.member_role_update,
                    target_id=after.id,
                )

                await self.record_event(
                    after.guild,
                    "role",
                    "Member roles updated",
                    f"Roles changed for {after.display_name}.",
                    changes,
                    event_type="member_roles_update",
                    actor_id=actor_id,
                    actor_name=actor_name,
                )

    # ---- message events -------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return

        actor_id, actor_name = await self.resolve_audit_actor(
            message.guild,
            discord.AuditLogAction.message_delete,
            target_id=message.author.id,
        )

        content_preview = (message.content or "").strip()
        if len(content_preview) > 180:
            content_preview = content_preview[:177] + "…"
        if not content_preview:
            content_preview = "(empty or embed-only message)"

        channel_name = getattr(message.channel, "name", "unknown")
        description = (
            f"A message by {message.author.display_name} was deleted in "
            f"#{channel_name}."
        )
        if actor_name and actor_id != str(message.author.id):
            description = (
                f"{actor_name} deleted a message by "
                f"{message.author.display_name} in #{channel_name}."
            )

        await self.record_event(
            message.guild,
            "message",
            "Message deleted",
            description,
            {
                "Author": f"{message.author} ({message.author.id})",
                "Channel": channel_name,
                "Content": content_preview,
            },
            event_type="message_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: discord.Message,
        after: discord.Message,
    ) -> None:
        if after.guild is None or after.author.bot:
            return

        if before.content == after.content:
            return

        channel_name = getattr(after.channel, "name", "unknown")
        await self.record_event(
            after.guild,
            "message",
            "Message edited",
            (
                f"{after.author.display_name} edited a message in "
                f"#{channel_name}."
            ),
            {
                "Author": f"{after.author} ({after.author.id})",
                "Channel": channel_name,
                "Before": (before.content or "—")[:512],
                "After": (after.content or "—")[:512],
            },
            event_type="message_edit",
            actor_id=str(after.author.id),
            actor_name=str(after.author),
        )

    # ---- role events ------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            role.guild,
            discord.AuditLogAction.role_create,
            target_id=role.id,
        )
        await self.record_event(
            role.guild,
            "role",
            "Role created",
            f"Role **{role.name}** was created.",
            {"Role": role.name},
            event_type="role_create",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            role.guild,
            discord.AuditLogAction.role_delete,
            target_id=role.id,
        )
        await self.record_event(
            role.guild,
            "role",
            "Role deleted",
            f"Role **{role.name}** was deleted.",
            {"Role": role.name},
            event_type="role_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ) -> None:
        try:
            await self._log_guild_role_update(before, after)
        except Exception:  # noqa: BLE001 - logging must never break the gateway
            logger.exception("Failed to log role update guild_id=%s", after.guild.id)

    async def _log_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ) -> None:
        detail = build_role_update_detail(before, after)
        if detail.is_empty():
            return

        permissions_changed = bool(detail.permission_changes)
        wait_s = 0.6 if permissions_changed else 0.0
        since = (
            datetime.now(timezone.utc) - timedelta(seconds=5)
            if permissions_changed
            else None
        )
        actor_id, actor_name, actor_status, reason = (
            await self._resolve_audit_actor_detailed(
                after.guild,
                discord.AuditLogAction.role_update,
                target_id=after.id,
                since=since,
                max_wait_s=wait_s,
            )
        )
        if actor_status not in {"found", "delayed"}:
            actor_id, actor_name = None, None
            reason = None
        detail.actor = (
            {"id": actor_id, "name": actor_name}
            if actor_id or actor_name
            else None
        )
        detail.reason = reason

        name_only = (
            len(detail.field_changes) == 1
            and detail.field_changes[0].field == "name"
            and not permissions_changed
        )
        perms_only = not detail.field_changes and permissions_changed
        if name_only:
            action = "Role renamed"
            description = (
                f"Role **{before.name}** renamed to **{after.name}**."
            )
        elif perms_only:
            action = "Role permissions updated"
            description = f"Permissions changed for role **{after.name}**."
        else:
            action = "Role updated"
            description = f"Role **{after.name}** was updated."

        fields: dict[str, str] = {
            "Role": after.name,
            "Role ID": str(after.id),
        }
        fields.update(discord_embed_field_changes(detail.field_changes))
        if permissions_changed:
            diff = diff_role_permissions(before.permissions, after.permissions)
            fields.update(role_permission_fields(diff))
            logger.info(
                "permission_diff event_type=%s guild_id=%s granted=%s revoked=%s "
                "overwrite_changes=%s actor_status=%s",
                "role_update",
                after.guild.id,
                len(diff.granted),
                len(diff.revoked),
                0,
                actor_status,
            )
        if actor_status not in {"found", "delayed"}:
            fields["Actor"] = actor_fallback_text(actor_status)

        await self.record_event(
            after.guild,
            "role",
            action,
            description,
            fields,
            event_type="role_update",
            actor_id=actor_id,
            actor_name=actor_name,
            detail=detail,
        )

    # ---- channel events ----------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self,
        channel: discord.abc.GuildChannel,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            channel.guild,
            discord.AuditLogAction.channel_create,
            target_id=channel.id,
        )
        await self.record_event(
            channel.guild,
            "channel",
            "Channel created",
            f"Channel **#{channel.name}** was created.",
            {"Type": str(channel.type)},
            event_type="channel_create",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self,
        channel: discord.abc.GuildChannel,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            target_id=channel.id,
        )
        await self.record_event(
            channel.guild,
            "channel",
            "Channel deleted",
            f"Channel **#{channel.name}** was deleted.",
            {"Type": str(channel.type)},
            event_type="channel_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        try:
            await self._log_guild_channel_update(before, after)
        except Exception:  # noqa: BLE001 - logging must never break the gateway
            logger.exception(
                "Failed to log channel update guild_id=%s", after.guild.id
            )

    async def _log_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        overwrite_diff = diff_channel_overwrites(before, after)
        detail = build_channel_update_detail(
            before,
            after,
            category_synced=overwrite_diff.category_synced,
        )
        if detail.is_empty():
            return

        overwrite_items = diff_channel_overwrite_items(before, after)
        overwrite_target_ids: set[int] = set()
        for item in overwrite_items:
            try:
                overwrite_target_ids.add(int(item.target_id))
            except (TypeError, ValueError):
                continue

        since = datetime.now(timezone.utc) - timedelta(seconds=5)
        actions: list[discord.AuditLogAction] = []
        overwrite_actions: list[discord.AuditLogAction] = []
        if overwrite_items or not overwrite_diff.is_empty():
            kinds = {item.change for item in overwrite_items}
            if "overwrite_added" in kinds:
                overwrite_actions.append(discord.AuditLogAction.overwrite_create)
            if "transition" in kinds or (
                not overwrite_items and not overwrite_diff.is_empty()
            ):
                overwrite_actions.append(discord.AuditLogAction.overwrite_update)
            if "overwrite_removed" in kinds:
                overwrite_actions.append(discord.AuditLogAction.overwrite_delete)
            if not overwrite_actions:
                overwrite_actions.append(discord.AuditLogAction.overwrite_update)
        if detail.field_changes:
            actions.append(discord.AuditLogAction.channel_update)
        actions = list(dict.fromkeys([*overwrite_actions, *actions]))[:3]
        if not actions:
            actions = [discord.AuditLogAction.channel_update]

        first_delay = 0.6 if overwrite_items else 0.4
        actor_id, actor_name, actor_status, reason = (
            await self._resolve_audit_actor_detailed(
                after.guild,
                actions[0],
                target_id=after.id,
                actions=actions,
                since=since,
                retry_delays=(0.0, first_delay, 1.2),
                overwrite_target_ids=overwrite_target_ids or None,
            )
        )
        logger.info(
            "channel_actor_status=%s guild_id=%s event_type=channel_update",
            actor_status,
            after.guild.id,
        )
        if actor_status not in {"found", "delayed"}:
            actor_id = None
            actor_name = None
            reason = None
        detail.actor = (
            {"id": actor_id, "name": actor_name}
            if actor_id or actor_name
            else None
        )
        detail.reason = reason

        fields: dict[str, str] = discord_embed_field_changes(detail.field_changes)
        fields["Channel"] = f"#{after.name}"
        fields["Channel ID"] = str(after.id)
        channel_type = getattr(after, "type", None)
        if channel_type is not None and "Type" not in fields:
            fields["Type"] = str(channel_type)
        fields.update(channel_overwrite_fields(overwrite_diff))
        if actor_status not in {"found", "delayed"}:
            fields["Actor"] = actor_fallback_text(actor_status)

        if not overwrite_diff.is_empty():
            logger.info(
                "permission_diff event_type=%s guild_id=%s granted=%s revoked=%s "
                "overwrite_changes=%s actor_status=%s",
                "channel_update",
                after.guild.id,
                len(overwrite_diff.granted),
                len(overwrite_diff.inherited),
                overwrite_diff.change_count(),
                actor_status,
            )

        recorded = await self.record_event(
            after.guild,
            "channel",
            "Channel updated",
            f"Channel **#{after.name}** was updated.",
            fields,
            event_type="channel_update",
            actor_id=actor_id,
            actor_name=actor_name,
            detail=detail,
        )
        if actor_status in {"unavailable", "rate_limited"}:
            self._schedule_channel_actor_enrichment(
                guild=after.guild,
                source_event_id=recorded.get("id"),
                posted=list(recorded.get("posted") or []),
                actions=actions,
                target_id=after.id,
                overwrite_target_ids=overwrite_target_ids,
                event_type="channel_update",
                category="channel",
                title="Channel updated",
                description=f"Channel **#{after.name}** was updated.",
                fields=recorded.get("fields") or fields,
                detail=detail,
            )

    # ---- thread events -----------------------------------------------------

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        parent_name = getattr(thread.parent, "name", "unknown")
        actor_id, actor_name = await self.resolve_audit_actor(
            thread.guild,
            discord.AuditLogAction.thread_create,
            target_id=thread.id,
        )
        await self.record_event(
            thread.guild,
            "thread",
            "Thread created",
            f"Thread **{thread.name}** was created in #{parent_name}.",
            {"Thread": thread.name, "Parent": parent_name},
            event_type="thread_create",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        parent_name = getattr(thread.parent, "name", "unknown")
        actor_id, actor_name = await self.resolve_audit_actor(
            thread.guild,
            discord.AuditLogAction.thread_delete,
            target_id=thread.id,
        )
        await self.record_event(
            thread.guild,
            "thread",
            "Thread deleted",
            f"Thread **{thread.name}** was deleted from #{parent_name}.",
            {"Thread": thread.name, "Parent": parent_name},
            event_type="thread_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_thread_update(
        self,
        before: discord.Thread,
        after: discord.Thread,
    ) -> None:
        detail = build_thread_update_detail(before, after)
        if detail.is_empty():
            return

        actor_id, actor_name, actor_status, reason = (
            await self._resolve_audit_actor_detailed(
                after.guild,
                discord.AuditLogAction.thread_update,
                target_id=after.id,
            )
        )
        if actor_status not in {"found", "delayed"}:
            actor_id, actor_name = None, None
            reason = None
        detail.actor = (
            {"id": actor_id, "name": actor_name}
            if actor_id or actor_name
            else None
        )
        detail.reason = reason

        fields = discord_embed_field_changes(detail.field_changes)
        fields["Thread"] = after.name
        fields["Thread ID"] = str(after.id)

        await self.record_event(
            after.guild,
            "thread",
            "Thread updated",
            f"Thread **{after.name}** was updated.",
            fields,
            event_type="thread_update",
            actor_id=actor_id,
            actor_name=actor_name,
            detail=detail,
        )

    # ---- ban events --------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(
        self,
        guild: discord.Guild,
        user: discord.User | discord.Member,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            guild,
            discord.AuditLogAction.ban,
            target_id=user.id,
        )
        await self.record_event(
            guild,
            "member",
            "Member banned",
            f"{user} ({user.id}) was banned.",
            {"Member": f"{user} ({user.id})"},
            event_type="member_ban",
            actor_id=actor_id,
            actor_name=actor_name,
            target_discord_user_id=str(user.id),
            target_username=getattr(user, "name", None) or str(user),
            target_display_name=getattr(user, "global_name", None),
        )

    @commands.Cog.listener()
    async def on_member_unban(
        self,
        guild: discord.Guild,
        user: discord.User,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            guild,
            discord.AuditLogAction.unban,
            target_id=user.id,
        )
        await self.record_event(
            guild,
            "member",
            "Member unbanned",
            f"{user} ({user.id}) was unbanned.",
            {"Member": f"{user} ({user.id})"},
            event_type="member_unban",
            actor_id=actor_id,
            actor_name=actor_name,
            target_discord_user_id=str(user.id),
            target_username=getattr(user, "name", None) or str(user),
            target_display_name=getattr(user, "global_name", None),
        )

    # ---- bulk message + server + voice events ------------------------------

    @commands.Cog.listener()
    async def on_bulk_message_delete(
        self,
        messages: list[discord.Message],
    ) -> None:
        if not messages:
            return
        guild = messages[0].guild
        if guild is None:
            return
        channel_name = getattr(messages[0].channel, "name", "unknown")
        await self.record_event(
            guild,
            "message",
            "Messages bulk deleted",
            f"{len(messages)} messages were bulk deleted in #{channel_name}.",
            {"Channel": channel_name, "Count": str(len(messages))},
            event_type="message_bulk_delete",
        )

    @commands.Cog.listener()
    async def on_guild_update(
        self,
        before: discord.Guild,
        after: discord.Guild,
    ) -> None:
        changes: dict[str, str] = {}
        if before.name != after.name:
            changes["Name"] = f"{before.name} → {after.name}"
        if before.owner_id != after.owner_id:
            changes["Owner"] = "changed"
        if not changes:
            return

        actor_id, actor_name = await self.resolve_audit_actor(
            after,
            discord.AuditLogAction.guild_update,
        )
        await self.record_event(
            after,
            "server",
            "Server settings updated",
            f"Server **{after.name}** settings were updated.",
            changes,
            event_type="guild_update",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel is None and after.channel is not None:
            await self.record_event(
                member.guild,
                "voice",
                "Joined voice",
                f"{member.display_name} joined voice **{after.channel.name}**.",
                {"Member": f"{member} ({member.id})", "Channel": after.channel.name},
                event_type="voice_join",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        elif before.channel is not None and after.channel is None:
            await self.record_event(
                member.guild,
                "voice",
                "Left voice",
                f"{member.display_name} left voice **{before.channel.name}**.",
                {"Member": f"{member} ({member.id})", "Channel": before.channel.name},
                event_type="voice_leave",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            await self.record_event(
                member.guild,
                "voice",
                "Moved voice channel",
                (
                    f"{member.display_name} moved from **{before.channel.name}** "
                    f"to **{after.channel.name}**."
                ),
                {
                    "Member": f"{member} ({member.id})",
                    "From": before.channel.name,
                    "To": after.channel.name,
                },
                event_type="voice_move",
                actor_id=str(member.id),
                actor_name=str(member),
            )

        if before.mute != after.mute:
            await self.record_event(
                member.guild,
                "voice",
                "Server mute toggled",
                (
                    f"{member.display_name} was "
                    f"{'server-muted' if after.mute else 'server-unmuted'}."
                ),
                {
                    "Member": f"{member} ({member.id})",
                    "Muted": "yes" if after.mute else "no",
                },
                event_type="voice_server_mute",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        if before.deaf != after.deaf:
            await self.record_event(
                member.guild,
                "voice",
                "Server deafen toggled",
                (
                    f"{member.display_name} was "
                    f"{'server-deafened' if after.deaf else 'server-undeafened'}."
                ),
                {
                    "Member": f"{member} ({member.id})",
                    "Deafened": "yes" if after.deaf else "no",
                },
                event_type="voice_server_deafen",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        if before.self_stream != after.self_stream or before.self_video != after.self_video:
            await self.record_event(
                member.guild,
                "voice",
                "Stream / camera toggled",
                f"{member.display_name} updated stream/camera state.",
                {
                    "Member": f"{member} ({member.id})",
                    "Streaming": "yes" if after.self_stream else "no",
                    "Camera": "yes" if after.self_video else "no",
                },
                event_type="voice_stream",
                actor_id=str(member.id),
                actor_name=str(member),
            )

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        if payload.cached_message is not None:
            return  # Handled by on_message_delete with richer content.
        if payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(payload.channel_id)
        channel_name = getattr(channel, "name", str(payload.channel_id))
        await self.record_event(
            guild,
            "message",
            "Message deleted (uncached)",
            f"A message was deleted in #{channel_name} (content unavailable).",
            {
                "Message ID": str(payload.message_id),
                "Channel": f"#{channel_name} ({payload.channel_id})",
            },
            event_type="message_delete_raw",
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None or payload.member is None or payload.member.bot:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        await self.record_event(
            guild,
            "message",
            "Reaction added",
            f"{payload.member.display_name} added {payload.emoji}.",
            {
                "Member": f"{payload.member} ({payload.user_id})",
                "Emoji": str(payload.emoji),
                "Message ID": str(payload.message_id),
                "Channel ID": str(payload.channel_id),
            },
            event_type="message_reaction_add",
            actor_id=str(payload.user_id),
            actor_name=str(payload.member),
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        await self.record_event(
            guild,
            "message",
            "Reaction removed",
            f"A reaction {payload.emoji} was removed.",
            {
                "User ID": str(payload.user_id),
                "Emoji": str(payload.emoji),
                "Message ID": str(payload.message_id),
                "Channel ID": str(payload.channel_id),
            },
            event_type="message_reaction_remove",
            actor_id=str(payload.user_id),
        )

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(
        self,
        channel: discord.abc.GuildChannel,
        last_pin: object | None,
    ) -> None:
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        await self.record_event(
            channel.guild,
            "channel",
            "Channel pins updated",
            f"Pins were updated in #{channel.name}.",
            {
                "Channel": f"#{channel.name} ({channel.id})",
                "Last pin": str(last_pin) if last_pin else "—",
            },
            event_type="channel_pins_update",
        )

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji],
    ) -> None:
        await self.record_event(
            guild,
            "server",
            "Emojis updated",
            f"Server emojis changed ({len(before)} → {len(after)}).",
            {"Before": str(len(before)), "After": str(len(after))},
            event_type="guild_emojis_update",
        )

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: list[discord.GuildSticker],
        after: list[discord.GuildSticker],
    ) -> None:
        await self.record_event(
            guild,
            "server",
            "Stickers updated",
            f"Server stickers changed ({len(before)} → {len(after)}).",
            {"Before": str(len(before)), "After": str(len(after))},
            event_type="guild_stickers_update",
        )

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel) -> None:
        await self.record_event(
            channel.guild,
            "server",
            "Webhooks updated",
            f"Webhooks changed in #{getattr(channel, 'name', channel.id)}.",
            {"Channel": f"{getattr(channel, 'name', channel.id)} ({channel.id})"},
            event_type="webhooks_update",
        )

    @commands.Cog.listener()
    async def on_thread_member_join(self, member: discord.ThreadMember) -> None:
        thread = member.thread
        if thread is None or thread.guild is None:
            return
        user = thread.guild.get_member(member.id)
        name = user.display_name if user else str(member.id)
        await self.record_event(
            thread.guild,
            "thread",
            "Member joined thread",
            f"{name} joined thread **{thread.name}**.",
            {
                "Member": f"{name} ({member.id})",
                "Thread": f"{thread.name} ({thread.id})",
            },
            event_type="thread_member_join",
            actor_id=str(member.id),
            actor_name=name,
        )

    @commands.Cog.listener()
    async def on_thread_member_remove(self, member: discord.ThreadMember) -> None:
        thread = member.thread
        if thread is None or thread.guild is None:
            return
        await self.record_event(
            thread.guild,
            "thread",
            "Member left thread",
            f"Member {member.id} left thread **{thread.name}**.",
            {
                "Member ID": str(member.id),
                "Thread": f"{thread.name} ({thread.id})",
            },
            event_type="thread_member_remove",
            actor_id=str(member.id),
        )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        if invite.guild is None or not isinstance(invite.guild, discord.Guild):
            return
        await self.record_event(
            invite.guild,
            "invites",
            "Invite created",
            f"Invite `{invite.code}` was created.",
            {
                "Code": invite.code,
                "Channel": str(getattr(invite.channel, "name", invite.channel_id)),
                "Inviter": str(invite.inviter) if invite.inviter else "—",
                "Max uses": str(invite.max_uses or "∞"),
            },
            event_type="invite_created",
            actor_id=str(invite.inviter.id) if invite.inviter else None,
            actor_name=str(invite.inviter) if invite.inviter else None,
        )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        if invite.guild is None or not isinstance(invite.guild, discord.Guild):
            return
        await self.record_event(
            invite.guild,
            "invites",
            "Invite deleted",
            f"Invite `{invite.code}` was deleted.",
            {
                "Code": invite.code,
                "Channel": str(getattr(invite.channel, "name", invite.channel_id)),
            },
            event_type="invite_deleted",
        )

    @commands.Cog.listener()
    async def on_auto_moderation_action_execution(
        self, execution: object
    ) -> None:
        guild = getattr(execution, "guild", None)
        if guild is None:
            return
        await self.record_event(
            guild,
            "security",
            "Discord AutoMod execution",
            "Discord AutoMod took an action.",
            {
                "Rule ID": str(getattr(execution, "rule_id", "")),
                "Action": str(getattr(getattr(execution, "action", None), "type", "")),
                "User ID": str(getattr(execution, "user_id", "")),
                "Channel ID": str(getattr(execution, "channel_id", None) or "—"),
            },
            event_type="discord_automod_execution",
            actor_id=str(getattr(execution, "user_id", "") or "") or None,
        )
