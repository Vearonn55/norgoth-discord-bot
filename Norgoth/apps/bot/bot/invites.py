"""Invite tracking: join attribution, inviter counters, /invites command.

Requires the bot to have the Manage Server permission to list invites.
"""

from __future__ import annotations

import asyncio
import json
import logging
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


def resolve_invite_delta(
    previous: dict[str, int],
    current: dict[str, int],
) -> tuple[str | None, str]:
    """Pick the invite code that explains a join, or an honest fallback.

    Returns ``(code, attribution)`` where attribution is one of
    ``attributed``, ``vanity``, ``deleted``, ``ambiguous``, ``unavailable``,
    ``unknown``.
    """

    increased = [
        code for code, uses in current.items() if uses > previous.get(code, 0)
    ]
    vanished = [code for code in previous if code not in current]
    if len(increased) > 1 or (not increased and len(vanished) > 1):
        return None, "ambiguous"
    if len(increased) == 1:
        code = increased[0]
        if code == "vanity":
            return "vanity", "vanity"
        return code, "attributed"
    if len(vanished) == 1:
        code = vanished[0]
        if code == "vanity":
            return "vanity", "vanity"
        return code, "deleted"
    return None, "unknown"


class InvitesCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        # code -> uses per guild; "vanity" is tracked as a pseudo-code.
        self._invite_cache: dict[int, dict[str, int]] = {}
        # code -> (inviter_id, inviter_name) captured at create / list time.
        self._invite_inviters: dict[int, dict[str, tuple[str | None, str | None]]] = {}
        self._guild_locks: dict[int, asyncio.Lock] = {}
        # Joins already attributed this session (guild_id, member_id).
        self._attributed: dict[tuple[int, int], tuple[str | None, str | None]] = {}

        # client.py calls resolve_inviter while rendering welcome messages.
        bot.resolve_inviter = self.resolve_inviter  # type: ignore[method-assign]

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._guild_locks:
            self._guild_locks[guild_id] = asyncio.Lock()
        return self._guild_locks[guild_id]

    # ---- invite cache ----------------------------------------------------

    async def fetch_invite_uses(self, guild: discord.Guild) -> dict[str, int] | None:
        """Current uses per invite code, or None when we lack permission."""

        try:
            invites = await guild.invites()
        except discord.Forbidden:
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
        for invite in invites:
            if invite.inviter:
                inviters[invite.code] = (str(invite.inviter.id), str(invite.inviter))
            elif invite.code not in inviters:
                inviters[invite.code] = (None, None)

        if "VANITY_URL" in guild.features:
            try:
                vanity = await guild.vanity_invite()
                if vanity is not None:
                    uses["vanity"] = vanity.uses or 0
            except discord.HTTPException:
                pass

        return uses

    async def prime_cache(self, guild: discord.Guild) -> None:
        uses = await self.fetch_invite_uses(guild)

        if uses is not None:
            self._invite_cache[guild.id] = uses

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

        cache = self._invite_cache.setdefault(invite.guild.id, {})
        cache[invite.code] = invite.uses or 0
        inviter_id = str(invite.inviter.id) if invite.inviter else None
        inviter_name = str(invite.inviter) if invite.inviter else None
        self._invite_inviters.setdefault(invite.guild.id, {})[invite.code] = (
            inviter_id,
            inviter_name,
        )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        if invite.guild is None:
            return

        uses = self._invite_cache.get(invite.guild.id, {}).pop(invite.code, 0)
        inviter_id, inviter_name = self._invite_inviters.get(
            invite.guild.id, {}
        ).pop(invite.code, (None, None))
        if invite.inviter:
            inviter_id = str(invite.inviter.id)
            inviter_name = str(invite.inviter)
        payload = json.dumps(
            {
                "uses": uses,
                "inviter_id": inviter_id,
                "inviter_name": inviter_name,
            }
        )
        try:
            await self.bot.state.redis.set(
                invite_tombstone_key(invite.guild.id, invite.code),
                payload,
                ex=TOMBSTONE_TTL_SECONDS,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist invite tombstone")

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

            current = await self.fetch_invite_uses(guild)

            if current is None:
                attribution = "unavailable"
            else:
                previous = self._invite_cache.get(guild.id, {})
                code, attribution = resolve_invite_delta(previous, current)
                self._invite_cache[guild.id] = current

                if attribution == "deleted" and code:
                    tombstone = await self._load_tombstone(guild.id, code)
                    if tombstone:
                        inviter_id = tombstone.get("inviter_id")
                        inviter_name = tombstone.get("inviter_name")
                        if inviter_id:
                            attribution = "attributed"
                elif attribution == "attributed" and code:
                    inviter_id, inviter_name = self._invite_inviters.get(
                        guild.id, {}
                    ).get(code, (None, None))
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
        )
        status = attribution_status(invite_code, inviter_id)
        fields["Attribution"] = status

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
