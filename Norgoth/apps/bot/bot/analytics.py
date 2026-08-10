"""Daily engagement analytics collectors → Redis buckets."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

logger = logging.getLogger("norgoth.bot.analytics")


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def daily_key(guild_id: int | str, day: str | None = None) -> str:
    return f"norgoth:guild:{guild_id}:analytics:daily:{day or _utc_day()}"


def authors_key(guild_id: int | str, day: str | None = None) -> str:
    return f"norgoth:guild:{guild_id}:analytics:authors:{day or _utc_day()}"


def voice_key(guild_id: int | str, day: str | None = None) -> str:
    return f"norgoth:guild:{guild_id}:analytics:voice:{day or _utc_day()}"


def known_members_key(guild_id: int | str) -> str:
    """All-time member ids, used to tell first-time joins from rejoins."""
    return f"norgoth:guild:{guild_id}:analytics:known_members"


# Keep daily keys for ~120 days
ANALYTICS_TTL_SECONDS = 120 * 24 * 60 * 60


class AnalyticsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _touch_ttl(self, *keys: str) -> None:
        redis = self.bot.state.redis
        for key in keys:
            await redis.expire(key, ANALYTICS_TTL_SECONDS)

    async def _inc_field(self, guild_id: int, field: str, amount: int = 1) -> None:
        key = daily_key(guild_id)
        redis = self.bot.state.redis
        await redis.hincrby(key, field, amount)
        await redis.expire(key, ANALYTICS_TTL_SECONDS)

    async def _snapshot_member_count(self, guild: discord.Guild) -> None:
        """Record today's total member count (last write wins per day).

        This gives the API a per-day population series to compute normalized
        net growth, churn, and retention — metrics that need the denominator
        (how many members existed), not just the join/leave deltas.
        """

        count = guild.member_count
        if count is None:
            return
        key = daily_key(guild.id)
        redis = self.bot.state.redis
        await redis.hset(key, "member_count", int(count))
        await redis.expire(key, ANALYTICS_TTL_SECONDS)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        redis = self.bot.state.redis
        day = _utc_day()
        dkey = daily_key(guild_id, day)
        akey = authors_key(guild_id, day)

        await redis.hincrby(dkey, "messages", 1)
        await redis.sadd(akey, str(message.author.id))
        unique = await redis.scard(akey)
        await redis.hset(dkey, "unique_authors", int(unique))
        await self._touch_ttl(dkey, akey)

    @commands.Cog.listener()
    async def on_guild_available(self, guild: discord.Guild) -> None:
        """Seed the all-time member set so pre-existing members are known.

        Without this, a member who was already in the guild before the bot
        started would be miscounted as a brand-new join when they return.
        The member cache may be empty when this fires, so request a chunk
        first (members intent is enabled).
        """
        try:
            if not guild.chunked:
                await guild.chunk()
        except (discord.ClientException, discord.HTTPException):
            logger.warning("Could not chunk guild %s for analytics bootstrap", guild.id)

        await self._snapshot_member_count(guild)

        members = [str(m.id) for m in guild.members if not m.bot]
        if not members:
            return
        redis = self.bot.state.redis
        await redis.sadd(known_members_key(guild.id), *members)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        # sadd returns the number of NEW elements added: 1 => first-time join,
        # 0 => the id was already known => this is a rejoin.
        redis = self.bot.state.redis
        added = await redis.sadd(known_members_key(member.guild.id), str(member.id))
        await self._inc_field(member.guild.id, "joins" if added else "rejoins")
        await self._snapshot_member_count(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return
        await self._inc_field(member.guild.id, "leaves")
        await self._snapshot_member_count(member.guild)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot or member.guild is None:
            return
        # Count unique participants who join a channel (not leave-only / mute toggles)
        joined = before.channel is None and after.channel is not None
        switched = (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        )
        if not (joined or switched):
            return

        guild_id = member.guild.id
        day = _utc_day()
        redis = self.bot.state.redis
        dkey = daily_key(guild_id, day)
        vkey = voice_key(guild_id, day)
        await redis.sadd(vkey, str(member.id))
        unique = await redis.scard(vkey)
        await redis.hset(dkey, "voice_uniques", int(unique))
        await self._touch_ttl(dkey, vkey)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnalyticsCog(bot))
