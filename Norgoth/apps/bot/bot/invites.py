"""Invite tracking: join attribution, inviter counters, /invites command.

Requires the bot to have the Manage Server permission to list invites.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from bot.state import now_iso
from bot.invite_log_render import (
    DEFAULT_JOIN_MESSAGE,
    DEFAULT_LEAVE_MESSAGE,
    attribution_status,
    build_invite_log_fields,
    build_template_context,
    render_invite_log_description,
)

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.invites")

RECENT_JOINS_CAP = 200
TOMBSTONE_TTL_SECONDS = 600


def invite_members_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:invites:members"


def invite_counters_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:invites:counters"


def invite_recent_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:invites:recent"


def invite_tombstone_key(guild_id: int | str, code: str) -> str:
    return f"norgoth:guild:{guild_id}:invites:tombstone:{code}"


def _snowflake_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.isdigit() and 1 <= len(text) <= 25:
        return text
    return None


def _is_one_use(meta: dict[str, Any] | None) -> bool:
    if not meta:
        return False
    if meta.get("invite_kind") == "one_use":
        return True
    max_uses = meta.get("max_uses")
    try:
        return int(max_uses) == 1
    except (TypeError, ValueError):
        return False


def classify_join_attribution(
    previous: dict[str, int],
    current: dict[str, int],
    *,
    vanished_meta: dict[str, dict[str, Any]] | None = None,
) -> tuple[str | None, str, str]:
    """Pick the invite code that explains a join.

    Returns ``(code, attribution, method)`` where method is one of
    ``usage_delta``, ``consumed_one_use``, ``tombstone``, ``vanity``.
    """

    meta = vanished_meta or {}
    increased = [
        code for code, uses in current.items() if uses > previous.get(code, 0)
    ]
    vanished = [code for code in previous if code not in current]
    if len(increased) > 1:
        return None, "ambiguous", "usage_delta"
    if len(increased) == 1:
        code = increased[0]
        if code == "vanity":
            return "vanity", "vanity", "vanity"
        return code, "attributed", "usage_delta"

    one_use_vanished = [
        code
        for code in vanished
        if code != "vanity" and _is_one_use(meta.get(code))
    ]
    if len(one_use_vanished) > 1:
        return None, "ambiguous", "consumed_one_use"
    if len(one_use_vanished) == 1:
        return one_use_vanished[0], "consumed_one_use", "consumed_one_use"

    if len(vanished) > 1:
        return None, "ambiguous", "tombstone"
    if len(vanished) == 1:
        code = vanished[0]
        if code == "vanity":
            return "vanity", "vanity", "vanity"
        return code, "deleted", "tombstone"
    return None, "unknown", "usage_delta"


def resolve_invite_delta(
    previous: dict[str, int],
    current: dict[str, int],
) -> tuple[str | None, str]:
    """Pick the invite code that explains a join, or an honest fallback.

    Returns ``(code, attribution)`` where attribution is one of
    ``attributed``, ``vanity``, ``deleted``, ``ambiguous``, ``unavailable``,
    ``unknown``.
    """

    code, attribution, _method = classify_join_attribution(previous, current)
    return code, attribution


class InvitesCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        # code -> uses per guild; "vanity" is tracked as a pseudo-code.
        self._invite_cache: dict[int, dict[str, int]] = {}
        # code -> (inviter_id, inviter_name) captured at create / list time.
        self._invite_inviters: dict[int, dict[str, tuple[str | None, str | None]]] = {}
        # code -> {max_uses, channel_id, uses, ...} captured at create / list time.
        self._invite_meta: dict[int, dict[str, dict[str, Any]]] = {}
        # vanished markers kept until join correlation or TTL.
        self._vanished: dict[int, dict[str, dict[str, Any]]] = {}
        self._guild_locks: dict[int, asyncio.Lock] = {}
        self._invite_forbidden_logged_at: dict[int, float] = {}
        # Joins already attributed this session (guild_id, member_id).
        self._attributed: dict[tuple[int, int], tuple[str | None, str | None]] = {}

        # client.py calls resolve_inviter while rendering welcome messages.
        bot.resolve_inviter = self.resolve_inviter  # type: ignore[method-assign]

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._guild_locks:
            self._guild_locks[guild_id] = asyncio.Lock()
        return self._guild_locks[guild_id]

    # ---- invite cache ----------------------------------------------------

    async def fetch_invite_uses(
        self,
        guild: discord.Guild,
        *,
        snapshot_out: list[dict[str, Any]] | None = None,
    ) -> dict[str, int] | None:
        """Current uses per invite code, or None when we lack permission."""

        try:
            invites = await guild.invites()
        except discord.Forbidden:
            now = time.monotonic()
            last = self._invite_forbidden_logged_at.get(guild.id, 0.0)
            if now - last >= 3600:
                self._invite_forbidden_logged_at[guild.id] = now
                logger.warning(
                    "Cannot list invites in guild %s: missing Manage Server.",
                    guild.id,
                )
            return None
        except discord.HTTPException:
            logger.exception("Failed to fetch invites for guild %s", guild.id)
            return None

        uses = {invite.code: invite.uses or 0 for invite in invites}
        inviters = self._invite_inviters.setdefault(guild.id, {})
        meta = self._invite_meta.setdefault(guild.id, {})
        for invite in invites:
            if invite.inviter:
                inviters[invite.code] = (str(invite.inviter.id), str(invite.inviter))
            elif invite.code not in inviters:
                inviters[invite.code] = (None, None)
            channel = getattr(invite, "channel", None)
            channel_id = str(channel.id) if channel is not None else None
            max_uses = getattr(invite, "max_uses", None)
            kind = (
                "vanity"
                if invite.code == "vanity"
                else ("one_use" if max_uses == 1 else "standard")
            )
            meta[invite.code] = {
                "max_uses": max_uses,
                "channel_id": channel_id,
                "uses": invite.uses or 0,
                "max_age": getattr(invite, "max_age", None),
                "temporary": bool(getattr(invite, "temporary", False)),
                "invite_kind": kind,
            }
            if snapshot_out is not None:
                inviter_id, inviter_name = inviters.get(invite.code, (None, None))
                snapshot_out.append(
                    {
                        "code": invite.code,
                        "inviter_id": inviter_id,
                        "inviter_name_snapshot": inviter_name,
                        "channel_id": channel_id,
                        "uses": invite.uses or 0,
                        "max_uses": max_uses,
                        "max_age": getattr(invite, "max_age", None),
                        "temporary": bool(getattr(invite, "temporary", False)),
                        "status": "active",
                        "invite_kind": kind,
                    }
                )

        if "VANITY_URL" in guild.features:
            try:
                vanity = await guild.vanity_invite()
                if vanity is not None:
                    uses["vanity"] = vanity.uses or 0
                    meta["vanity"] = {
                        "max_uses": None,
                        "channel_id": None,
                        "uses": vanity.uses or 0,
                        "invite_kind": "vanity",
                    }
                    if snapshot_out is not None:
                        snapshot_out.append(
                            {
                                "code": "vanity",
                                "uses": vanity.uses or 0,
                                "status": "active",
                                "invite_kind": "vanity",
                            }
                        )
            except discord.HTTPException:
                pass

        return uses

    async def prime_cache(self, guild: discord.Guild) -> None:
        snapshot: list[dict[str, Any]] = []
        uses = await self.fetch_invite_uses(guild, snapshot_out=snapshot)

        if uses is None:
            return
        async with self.get_lock(guild.id):
            self._invite_cache[guild.id] = uses
            keep = set(uses) | set(self._vanished.get(guild.id, {}))
            inviters = self._invite_inviters.setdefault(guild.id, {})
            for code in list(inviters):
                if code not in keep:
                    del inviters[code]
            meta = self._invite_meta.setdefault(guild.id, {})
            for code in list(meta):
                if code not in keep:
                    del meta[code]
        if snapshot:
            await self._ingest_invite_lifecycle_snapshot(guild.id, snapshot)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            await self.prime_cache(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.prime_cache(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        if invite.guild is None:
            return

        inviter_id = str(invite.inviter.id) if invite.inviter else None
        inviter_name = str(invite.inviter) if invite.inviter else None
        channel = getattr(invite, "channel", None)
        channel_id = str(channel.id) if channel is not None else None
        max_uses = getattr(invite, "max_uses", None)
        kind = "one_use" if max_uses == 1 else "standard"
        async with self.get_lock(invite.guild.id):
            cache = self._invite_cache.setdefault(invite.guild.id, {})
            cache[invite.code] = invite.uses or 0
            self._invite_inviters.setdefault(invite.guild.id, {})[invite.code] = (
                inviter_id,
                inviter_name,
            )
            self._invite_meta.setdefault(invite.guild.id, {})[invite.code] = {
                "max_uses": max_uses,
                "channel_id": channel_id,
                "uses": invite.uses or 0,
                "max_age": getattr(invite, "max_age", None),
                "temporary": bool(getattr(invite, "temporary", False)),
                "invite_kind": kind,
            }
            self._vanished.get(invite.guild.id, {}).pop(invite.code, None)
        await self._ingest_invite_lifecycle(
            invite.guild.id,
            {
                "code": invite.code,
                "inviter_id": inviter_id,
                "inviter_name_snapshot": inviter_name,
                "channel_id": channel_id,
                "uses": invite.uses or 0,
                "max_uses": max_uses,
                "max_age": getattr(invite, "max_age", None),
                "temporary": bool(getattr(invite, "temporary", False)),
                "status": "active",
                "invite_kind": kind,
            },
        )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        if invite.guild is None:
            return

        disappeared_at = datetime.now(timezone.utc).isoformat()
        async with self.get_lock(invite.guild.id):
            cache = self._invite_cache.setdefault(invite.guild.id, {})
            uses = cache.get(invite.code, invite.uses or 0)
            inviter_id, inviter_name = self._invite_inviters.get(
                invite.guild.id, {}
            ).get(invite.code, (None, None))
            if invite.inviter:
                inviter_id = str(invite.inviter.id)
                inviter_name = str(invite.inviter)
                self._invite_inviters.setdefault(invite.guild.id, {})[invite.code] = (
                    inviter_id,
                    inviter_name,
                )
            meta = dict(self._invite_meta.get(invite.guild.id, {}).get(invite.code) or {})
            max_uses = getattr(invite, "max_uses", None)
            if max_uses is None:
                max_uses = meta.get("max_uses")
            channel = getattr(invite, "channel", None)
            channel_id = (
                str(channel.id) if channel is not None else meta.get("channel_id")
            )
            kind = (
                "one_use"
                if max_uses == 1 or meta.get("invite_kind") == "one_use"
                else "standard"
            )
            status = "consumed" if kind == "one_use" else "deleted"
            vanished = {
                "uses": uses,
                "inviter_id": inviter_id,
                "inviter_name": inviter_name,
                "max_uses": max_uses,
                "channel_id": channel_id,
                "invite_kind": kind,
                "disappeared_at": disappeared_at,
            }
            self._vanished.setdefault(invite.guild.id, {})[invite.code] = vanished
            cache.pop(invite.code, None)
            payload = json.dumps(vanished)
        try:
            await self.bot.state.redis.set(
                invite_tombstone_key(invite.guild.id, invite.code),
                payload,
                ex=TOMBSTONE_TTL_SECONDS,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist invite tombstone")
        await self._ingest_invite_lifecycle(
            invite.guild.id,
            {
                "code": invite.code,
                "inviter_id": inviter_id,
                "inviter_name_snapshot": inviter_name,
                "channel_id": channel_id,
                "uses": uses,
                "max_uses": max_uses,
                "status": status,
                "invite_kind": kind,
                "disappeared_at": disappeared_at,
            },
        )

    # ---- attribution ---------------------------------------------------

    async def attribute_join(
        self,
        member: discord.Member,
    ) -> tuple[str | None, str | None]:
        """Determine which invite brought a member; idempotent per join.

        Returns (inviter_id, invite_code); either may be None when unknown.
        """

        guild = member.guild
        key = (guild.id, member.id)

        async with self.get_lock(guild.id):
            if key in self._attributed:
                return self._attributed[key]

            inviter_id: str | None = None
            inviter_name: str | None = None
            code: str | None = None
            attribution = "unavailable"
            method = "usage_delta"

            current = await self.fetch_invite_uses(guild)

            if current is None:
                attribution = "unavailable"
            else:
                self._expire_vanished(guild.id)
                previous = dict(self._invite_cache.get(guild.id, {}))
                vanished_meta: dict[str, dict[str, Any]] = {}
                for stored_code, row in self._invite_meta.get(guild.id, {}).items():
                    vanished_meta[stored_code] = dict(row)
                for stored_code, row in self._vanished.get(guild.id, {}).items():
                    previous.setdefault(stored_code, int(row.get("uses") or 0))
                    merged = dict(vanished_meta.get(stored_code) or {})
                    merged.update(row)
                    vanished_meta[stored_code] = merged
                code, attribution, method = classify_join_attribution(
                    previous,
                    current,
                    vanished_meta=vanished_meta,
                )
                self._invite_cache[guild.id] = current

                if attribution in {"unknown", "unavailable"}:
                    lifecycle = await self._load_recent_vanished_lifecycle(guild.id)
                    for row in lifecycle:
                        vanished_code = str(row.get("code") or "")
                        if not vanished_code or vanished_code in current:
                            continue
                        previous.setdefault(
                            vanished_code, int(row.get("uses") or 0)
                        )
                        vanished_meta[vanished_code] = {
                            **vanished_meta.get(vanished_code, {}),
                            **row,
                            "inviter_name": row.get("inviter_name"),
                        }
                    code, attribution, method = classify_join_attribution(
                        previous,
                        current,
                        vanished_meta=vanished_meta,
                    )

                if attribution in {"deleted", "consumed_one_use"} and code:
                    hint = (
                        self._vanished.get(guild.id, {}).get(code)
                        or vanished_meta.get(code)
                        or await self._load_tombstone(guild.id, code)
                    )
                    if hint:
                        inviter_id = _snowflake_or_none(hint.get("inviter_id")) or inviter_id
                        inviter_name = hint.get("inviter_name") or hint.get(
                            "inviter_name_snapshot"
                        )
                    if not inviter_id:
                        stored = self._invite_inviters.get(guild.id, {}).get(
                            code, (None, None)
                        )
                        inviter_id = _snowflake_or_none(stored[0]) or inviter_id
                        inviter_name = stored[1] or inviter_name
                    await self._consume_vanished(guild.id, code)
                elif attribution == "attributed" and code:
                    inviter_id, inviter_name = self._invite_inviters.get(
                        guild.id, {}
                    ).get(code, (None, None))
                    inviter_id = _snowflake_or_none(inviter_id)
                    if not inviter_id:
                        try:
                            invites = await guild.invites()
                            matched = next(
                                (inv for inv in invites if inv.code == code),
                                None,
                            )
                            if matched and matched.inviter:
                                inviter_id = str(matched.inviter.id)
                                inviter_name = str(matched.inviter)
                                self._invite_inviters.setdefault(guild.id, {})[
                                    code
                                ] = (inviter_id, inviter_name)
                        except discord.HTTPException:
                            pass
                    if not inviter_id:
                        attribution = "unknown"

            logger.info(
                "invite_attribution=%s method=%s guild_id=%s",
                attribution,
                method,
                guild.id,
            )

            await self.store_join(
                member,
                inviter_id=inviter_id,
                inviter_name=inviter_name,
                code=code,
                attribution=attribution,
            )

            result = (inviter_id, code)
            self._attributed[key] = result

            if len(self._attributed) > 2000:
                self._attributed.clear()

            return result

    def _expire_vanished(self, guild_id: int) -> None:
        vanished = self._vanished.get(guild_id, {})
        now = datetime.now(timezone.utc)
        for code in list(vanished):
            raw = vanished[code].get("disappeared_at")
            if not raw:
                continue
            try:
                disappeared = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                vanished.pop(code, None)
                continue
            if disappeared.tzinfo is None:
                disappeared = disappeared.replace(tzinfo=timezone.utc)
            if (now - disappeared).total_seconds() > TOMBSTONE_TTL_SECONDS:
                vanished.pop(code, None)

    async def _consume_vanished(self, guild_id: int, code: str) -> None:
        self._vanished.get(guild_id, {}).pop(code, None)
        self._invite_cache.get(guild_id, {}).pop(code, None)
        try:
            await self.bot.state.redis.delete(invite_tombstone_key(guild_id, code))
        except Exception:  # noqa: BLE001
            logger.debug(
                "Failed to delete invite tombstone guild_id=%s",
                guild_id,
                exc_info=True,
            )

    async def _load_tombstone(
        self, guild_id: int, code: str
    ) -> dict[str, Any] | None:
        raw = await self.bot.state.redis.get(invite_tombstone_key(guild_id, code))
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    async def store_join(
        self,
        member: discord.Member,
        *,
        inviter_id: str | None,
        inviter_name: str | None,
        code: str | None,
        attribution: str = "unknown",
    ) -> dict[str, Any]:
        redis = self.bot.state.redis
        guild = member.guild

        previous_raw = await redis.hget(
            invite_members_key(guild.id), str(member.id)
        )
        is_rejoin = previous_raw is not None

        record = {
            "member_id": str(member.id),
            "member_name": str(member),
            "inviter_id": inviter_id,
            "inviter_name": inviter_name,
            "code": code,
            "attribution": attribution,
            "rejoin": is_rejoin,
            "joined_at": now_iso(),
            "left_at": None,
        }

        await redis.hset(
            invite_members_key(guild.id),
            str(member.id),
            json.dumps(record),
        )

        try:
            await self.bot.state.append_capped_list(
                invite_recent_key(guild.id),
                record,
                cap=RECENT_JOINS_CAP,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to append recent join")

        if inviter_id:
            pause_credit = await redis.get(
                f"norgoth:guild:{guild.id}:raid:pause_invite_credit"
            )
            if not pause_credit:
                await self.bump_counter(
                    guild.id,
                    inviter_id,
                    inviter_name or inviter_id,
                    joins=1,
                    rejoins=1 if is_rejoin else 0,
                )

        await self._ingest_invite_join(guild.id, record)
        return record

    async def _ingest_invite_join(self, guild_id: int, record: dict[str, Any]) -> None:
        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if not base or not token:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{base}/internal/ingest/{guild_id}/invite-join",
                    headers={
                        "X-Norgoth-Internal-Token": token,
                        "X-Norgoth-Bot-Token": token,
                    },
                    json={
                        "member_id": record.get("member_id"),
                        "inviter_id": record.get("inviter_id"),
                        "code": record.get("code"),
                        "attribution": record.get("attribution") or "unknown",
                        "rejoin": bool(record.get("rejoin")),
                        "joined_at": record.get("joined_at"),
                        "inviter_name": record.get("inviter_name"),
                    },
                )
        except Exception:  # noqa: BLE001
            logger.debug("Invite join ingest failed for guild %s", guild_id, exc_info=True)

    def _ingest_headers(self) -> tuple[str, str] | None:
        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if not base or not token:
            return None
        return base, token

    async def _ingest_invite_lifecycle(
        self,
        guild_id: int,
        body: dict[str, Any],
    ) -> None:
        creds = self._ingest_headers()
        if creds is None:
            return
        base, token = creds
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{base}/internal/ingest/{guild_id}/invite-lifecycle",
                    headers={
                        "X-Norgoth-Internal-Token": token,
                        "X-Norgoth-Bot-Token": token,
                    },
                    json=body,
                )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Invite lifecycle ingest failed for guild %s",
                guild_id,
                exc_info=True,
            )

    async def _ingest_invite_lifecycle_snapshot(
        self,
        guild_id: int,
        invites: list[dict[str, Any]],
    ) -> None:
        creds = self._ingest_headers()
        if creds is None or not invites:
            return
        base, token = creds
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{base}/internal/ingest/{guild_id}/invite-lifecycle/snapshot",
                    headers={
                        "X-Norgoth-Internal-Token": token,
                        "X-Norgoth-Bot-Token": token,
                    },
                    json={"invites": invites},
                )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Invite lifecycle snapshot ingest failed for guild %s",
                guild_id,
                exc_info=True,
            )

    async def _load_recent_vanished_lifecycle(
        self, guild_id: int
    ) -> list[dict[str, Any]]:
        creds = self._ingest_headers()
        if creds is None:
            return []
        base, token = creds
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{base}/internal/ingest/{guild_id}/invite-lifecycle/recent-vanished",
                    headers={
                        "X-Norgoth-Internal-Token": token,
                        "X-Norgoth-Bot-Token": token,
                    },
                    params={"since_seconds": TOMBSTONE_TTL_SECONDS},
                )
            if response.status_code != 200:
                return []
            data = response.json()
            invites = data.get("invites") if isinstance(data, dict) else None
            if not isinstance(invites, list):
                return []
            return [row for row in invites if isinstance(row, dict)]
        except Exception:  # noqa: BLE001
            logger.debug(
                "Invite lifecycle lookup failed for guild %s",
                guild_id,
                exc_info=True,
            )
            return []

    async def _log_invite_event(
        self,
        guild: discord.Guild,
        *,
        kind: str,
        event_type: str,
        action: str,
        member_id: str,
        member_name: str,
        member_username: str | None,
        inviter_id: str | None,
        inviter_name: str | None,
        invite_code: str | None,
        joined_at: str | None,
        left_at: str | None = None,
        attribution: str | None = None,
    ) -> None:
        """Route an invite attribution event through central logging."""

        if not await self.bot.state.is_module_enabled(guild.id, "invites"):
            return

        cog = self.bot.get_cog("ServerLoggingCog")
        if cog is None:
            return

        inviter_count: int | None = None
        inviter_in_guild: bool | None = None
        if inviter_id:
            inviter_count = await self.get_inviter_count(guild.id, str(inviter_id))
            try:
                inviter_in_guild = guild.get_member(int(inviter_id)) is not None
            except (TypeError, ValueError):
                inviter_in_guild = None

        template = (
            DEFAULT_JOIN_MESSAGE if kind == "join" else DEFAULT_LEAVE_MESSAGE
        )
        context = build_template_context(
            kind="join" if kind == "join" else "leave",
            guild_name=guild.name,
            member_id=member_id,
            member_name=member_name,
            member_username=member_username,
            inviter_id=str(inviter_id) if inviter_id else None,
            inviter_name=inviter_name,
            inviter_count=inviter_count,
            invite_code=invite_code,
            joined_at=joined_at,
            left_at=left_at,
            inviter_in_guild=inviter_in_guild,
            attribution=attribution,
        )
        description = render_invite_log_description(
            kind="join" if kind == "join" else "leave",
            template=template,
            context=context,
        )
        fields = build_invite_log_fields(
            kind="join" if kind == "join" else "leave",
            member_name=member_name,
            member_id=member_id,
            inviter_id=str(inviter_id) if inviter_id else None,
            inviter_name=inviter_name,
            inviter_count=inviter_count,
            invite_code=invite_code,
            joined_at=joined_at,
            left_at=left_at,
            inviter_in_guild=inviter_in_guild,
            attribution=attribution,
        )
        fields["Attribution"] = attribution_status(
            invite_code, inviter_id, stored=attribution
        )

        try:
            await cog.record_event(
                guild,
                "invites",
                action,
                description,
                fields,
                event_type=event_type,
                actor_id=member_id,
                actor_name=member_name,
            )
        except Exception:  # noqa: BLE001 - logging must never break invite tracking
            logger.exception("Failed to record invite log event %s", event_type)

    # ---- join/leave listeners --------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        if not await self.bot.state.is_module_enabled(member.guild.id, "invites"):
            return

        inviter_id, code = await self.attribute_join(member)

        # Prefer the freshly stored Redis record for joined_at / inviter_name.
        raw = await self.bot.state.redis.hget(
            invite_members_key(member.guild.id), str(member.id)
        )
        record: dict[str, Any] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    record = parsed
            except json.JSONDecodeError:
                pass

        await self._log_invite_event(
            member.guild,
            kind="join",
            event_type="invite_member_joined",
            action="Member joined via invite",
            member_id=str(member.id),
            member_name=str(member),
            member_username=getattr(member, "name", None),
            inviter_id=record.get("inviter_id") or inviter_id,
            inviter_name=record.get("inviter_name"),
            invite_code=record.get("code") or code,
            joined_at=record.get("joined_at"),
            attribution=record.get("attribution"),
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return

        guild = member.guild
        redis = self.bot.state.redis

        raw = await redis.hget(invite_members_key(guild.id), str(member.id))

        if not raw:
            return

        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            return

        if not isinstance(record, dict):
            return

        # Idempotency: already-closed leave must not re-bump or re-log.
        if record.get("left_at"):
            return

        # Leave attribution logs require Invite Tracking to be enabled so we
        # do not emit stale attribution while the module is off.
        module_on = await self.bot.state.is_module_enabled(guild.id, "invites")

        left_at = now_iso()
        record["left_at"] = left_at
        await redis.hset(
            invite_members_key(guild.id),
            str(member.id),
            json.dumps(record),
        )

        inviter_id = record.get("inviter_id")

        if inviter_id:
            await self.bump_counter(
                guild.id,
                str(inviter_id),
                str(record.get("inviter_name") or inviter_id),
                leaves=1,
            )

        # Allow re-attribution if the member rejoins in this session.
        self._attributed.pop((guild.id, member.id), None)

        if module_on:
            await self._log_invite_event(
                guild,
                kind="leave",
                event_type="invite_member_left",
                action="Member left — invite attribution",
                member_id=str(member.id),
                member_name=str(record.get("member_name") or member),
                member_username=getattr(member, "name", None),
                inviter_id=str(inviter_id) if inviter_id else None,
                inviter_name=record.get("inviter_name"),
                invite_code=record.get("code"),
                joined_at=record.get("joined_at"),
                left_at=left_at,
                attribution=record.get("attribution"),
            )

    async def bump_counter(
        self,
        guild_id: int,
        inviter_id: str,
        inviter_name: str,
        *,
        joins: int = 0,
        leaves: int = 0,
        rejoins: int = 0,
    ) -> None:
        redis = self.bot.state.redis
        raw = await redis.hget(invite_counters_key(guild_id), inviter_id)

        counter = {"name": inviter_name, "joins": 0, "leaves": 0, "rejoins": 0}

        if raw:
            try:
                stored = json.loads(raw)
                if isinstance(stored, dict):
                    counter.update(stored)
            except json.JSONDecodeError:
                pass

        counter["name"] = inviter_name
        counter["joins"] = int(counter.get("joins", 0)) + joins
        counter["leaves"] = int(counter.get("leaves", 0)) + leaves
        counter["rejoins"] = int(counter.get("rejoins", 0)) + rejoins

        await redis.hset(
            invite_counters_key(guild_id),
            inviter_id,
            json.dumps(counter),
        )

    async def get_inviter_count(self, guild_id: int, inviter_id: str) -> int:
        raw = await self.bot.state.redis.hget(
            invite_counters_key(guild_id), inviter_id
        )

        if not raw:
            return 0

        try:
            counter = json.loads(raw)
        except json.JSONDecodeError:
            return 0

        if not isinstance(counter, dict):
            return 0

        return max(
            0,
            int(counter.get("joins", 0)) - int(counter.get("leaves", 0)),
        )

    async def resolve_inviter(
        self,
        member: discord.Member,
    ) -> tuple[str | None, int | None]:
        """Used by welcome messages for {inviter} / {inviter_count}."""

        if not await self.bot.state.is_module_enabled(member.guild.id, "invites"):
            return (None, None)

        inviter_id, _code = await self.attribute_join(member)

        if not inviter_id:
            return (None, None)

        raw = await self.bot.state.redis.hget(
            invite_counters_key(member.guild.id), inviter_id
        )

        name = None

        if raw:
            try:
                counter = json.loads(raw)
                if isinstance(counter, dict):
                    name = counter.get("name")
            except json.JSONDecodeError:
                pass

        count = await self.get_inviter_count(member.guild.id, inviter_id)
        return (name or inviter_id, count)

    # ---- slash command ------------------------------------------------------

    @app_commands.command(
        name="invites",
        description="Show how many members someone has invited",
    )
    @app_commands.describe(member="Member to look up (defaults to you)")
    async def invites_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        target = member or interaction.user
        raw = await self.bot.state.redis.hget(
            invite_counters_key(interaction.guild.id), str(target.id)
        )

        counter = {"joins": 0, "leaves": 0, "rejoins": 0}

        if raw:
            try:
                stored = json.loads(raw)
                if isinstance(stored, dict):
                    counter.update(stored)
            except json.JSONDecodeError:
                pass

        joins = int(counter.get("joins", 0))
        leaves = int(counter.get("leaves", 0))
        rejoins = int(counter.get("rejoins", 0))
        net = max(0, joins - leaves)

        embed = discord.Embed(
            title=f"Invites — {target.display_name}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Invites", value=str(net))
        embed.add_field(name="Joins", value=str(joins))
        embed.add_field(name="Left", value=str(leaves))
        embed.add_field(name="Rejoins", value=str(rejoins))

        await interaction.response.send_message(embed=embed)
