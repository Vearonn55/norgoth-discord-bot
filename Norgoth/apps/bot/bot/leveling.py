"""Level & activity system: XP per message, level-ups, and role rewards."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.leveling")

XP_COOLDOWN_SECONDS = 60

# Bounds must stay in sync with LevelingConfig in apps/api/app/routes/leveling.py.
XP_PER_MESSAGE_MIN = 1
XP_PER_MESSAGE_MAX = 100
XP_MULTIPLIER_MIN = 0.1
XP_MULTIPLIER_MAX = 5.0
DEFAULT_XP_PER_MESSAGE = 15
DEFAULT_XP_MULTIPLIER = 1.0

DEFAULT_CONFIG: dict[str, Any] = {
    "announce_mode": "current",  # "current" | "channel" | "off"
    "announce_channel_id": None,
    "xp_per_message": DEFAULT_XP_PER_MESSAGE,
    "xp_multiplier": DEFAULT_XP_MULTIPLIER,
    "level_up_message": "🎉 {user} reached level **{level}**!",
    "level_up_embed": {},
    "reward_roles": [],  # [{"level": 5, "role_id": "..."}]
}


def effective_xp(config: dict[str, Any]) -> int:
    """Compute XP awarded per eligible message from guild config.

    ``effective = base_xp * multiplier`` (rounded, minimum 1). The multiplier
    only scales reward magnitude; message eligibility is gated separately by
    the cooldown / anti-spam check and is unaffected here.
    """

    try:
        base = int(config.get("xp_per_message", DEFAULT_XP_PER_MESSAGE))
    except (TypeError, ValueError):
        base = DEFAULT_XP_PER_MESSAGE
    base = max(XP_PER_MESSAGE_MIN, min(XP_PER_MESSAGE_MAX, base))

    try:
        multiplier = float(config.get("xp_multiplier", DEFAULT_XP_MULTIPLIER))
    except (TypeError, ValueError):
        multiplier = DEFAULT_XP_MULTIPLIER
    multiplier = max(XP_MULTIPLIER_MIN, min(XP_MULTIPLIER_MAX, multiplier))

    return max(1, round(base * multiplier))


def leveling_config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:leveling:config"


def xp_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:xp"


def xp_cooldown_key(guild_id: int | str, user_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:xp:cooldown:{user_id}"


def xp_for_level(level: int) -> int:
    """Total XP required to reach a level (cumulative, MEE6-style curve)."""

    total = 0
    for step in range(level):
        total += 5 * step**2 + 50 * step + 100
    return total


def level_from_xp(xp: int) -> int:
    level = 0
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


class LevelingCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(leveling_config_key(guild_id))
        return {**DEFAULT_CONFIG, **stored}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (
            message.guild is None
            or message.author.bot
            or not isinstance(message.author, discord.Member)
        ):
            return

        guild = message.guild

        if not await self.bot.state.is_module_enabled(guild.id, "leveling"):
            return

        redis = self.bot.state.redis

        # SET NX doubles as an atomic cooldown gate. This eligibility check is
        # independent of the XP multiplier, so tuning rewards can never bypass
        # anti-spam.
        awarded = await redis.set(
            xp_cooldown_key(guild.id, message.author.id),
            "1",
            ex=XP_COOLDOWN_SECONDS,
            nx=True,
        )

        if not awarded:
            return

        config = await self.get_config(guild.id)

        previous_xp = await redis.zscore(xp_key(guild.id), str(message.author.id))
        previous_xp = int(previous_xp or 0)

        gain = effective_xp(config)
        new_xp = int(
            await redis.zincrby(xp_key(guild.id), gain, str(message.author.id))
        )

        old_level = level_from_xp(previous_xp)
        new_level = level_from_xp(new_xp)

        if new_level > old_level:
            await self.handle_level_up(message.author, new_level, message.channel)

    async def handle_level_up(
        self,
        member: discord.Member,
        new_level: int,
        announce_channel: discord.abc.Messageable | None = None,
    ) -> None:
        guild = member.guild

        config = await self.get_config(guild.id)

        # Role rewards for every configured level at or below the new one.
        for reward in config.get("reward_roles", []):
            try:
                reward_level = int(reward.get("level", 0))
                role_id = int(reward.get("role_id", 0))
            except (TypeError, ValueError):
                continue

            if reward_level > new_level or role_id == 0:
                continue

            role = guild.get_role(role_id)

            if role is None or role in member.roles:
                continue

            if guild.me is None or role >= guild.me.top_role:
                logger.warning(
                    "Cannot grant reward role %s in guild %s: above bot's "
                    "top role (or bot member missing)",
                    role.name if role else role_id,
                    guild.id,
                )
                continue

            try:
                await member.add_roles(
                    role, reason=f"Level {reward_level} reward"
                )
                logger.info(
                    "Granted reward role %s to %s in guild %s (level %s)",
                    role.id,
                    member.id,
                    guild.id,
                    reward_level,
                )
            except discord.Forbidden:
                logger.warning(
                    "Missing Manage Roles permission to grant role %s in guild %s",
                    role_id,
                    guild.id,
                )
            except discord.HTTPException:
                logger.exception("Failed to grant reward role %s", role_id)

        announce_mode = config.get("announce_mode", "current")

        if announce_mode == "off":
            return

        target_channel: discord.abc.Messageable | None = None

        if announce_mode == "channel" and config.get("announce_channel_id"):
            channel = guild.get_channel(int(config["announce_channel_id"]))
            if isinstance(channel, discord.TextChannel):
                target_channel = channel

        if target_channel is None:
            target_channel = announce_channel

        if target_channel is None:
            return

        # Level-up messages are always sent as an embed. The embed description
        # is the single source of truth for the message body; fall back to the
        # legacy `level_up_message` for older configs that never set it.
        embed_cfg = config.get("level_up_embed")
        if not isinstance(embed_cfg, dict):
            embed_cfg = {}

        def _sub(value: object) -> str:
            return (
                str(value or "")
                .replace("{user}", member.mention)
                .replace("{username}", member.display_name)
                .replace("{level}", str(new_level))
                .replace("{server}", guild.name)
            )

        description_source = (
            embed_cfg.get("description")
            or config.get("level_up_message")
            or DEFAULT_CONFIG["level_up_message"]
        )

        color_raw = embed_cfg.get("color")
        color = 0x5865F2
        if isinstance(color_raw, int):
            color = color_raw
        elif isinstance(color_raw, str):
            hex_value = color_raw.strip().lstrip("#")
            if len(hex_value) == 6:
                try:
                    color = int(hex_value, 16)
                except ValueError:
                    pass

        embed = discord.Embed(
            title=_sub(embed_cfg.get("title"))[:256] or None,
            description=_sub(description_source)[:4096] or None,
            color=color,
        )
        footer = _sub(embed_cfg.get("footer"))
        if footer:
            embed.set_footer(text=footer[:2048])
        thumb = str(embed_cfg.get("thumbnail_url") or "").strip()
        if thumb:
            embed.set_thumbnail(url=thumb)
        image = str(embed_cfg.get("image_url") or "").strip()
        if image:
            embed.set_image(url=image)
        for field in embed_cfg.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = _sub(field.get("name"))[:256]
            value = _sub(field.get("value"))[:1024]
            if name and value:
                embed.add_field(
                    name=name,
                    value=value,
                    inline=bool(field.get("inline")),
                )

        try:
            await target_channel.send(embed=embed)
        except discord.HTTPException:
            logger.exception("Failed to send level-up message")

    # ---- slash commands ------------------------------------------------------

    @app_commands.command(name="rank", description="Show your (or a member's) level and XP")
    @app_commands.describe(member="Member to look up (defaults to you)")
    async def rank(
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
        redis = self.bot.state.redis
        key = xp_key(interaction.guild.id)

        xp = await redis.zscore(key, str(target.id))
        xp = int(xp or 0)
        level = level_from_xp(xp)
        rank = await redis.zrevrank(key, str(target.id))

        current_floor = xp_for_level(level)
        next_requirement = xp_for_level(level + 1)

        embed = discord.Embed(
            title=f"Rank — {target.display_name}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="XP", value=f"{xp:,}")
        embed.add_field(
            name="Progress",
            value=f"{xp - current_floor:,} / {next_requirement - current_floor:,}",
        )
        embed.add_field(
            name="Server rank",
            value=f"#{rank + 1}" if rank is not None else "Unranked",
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="give-xp",
        description="Grant XP to a member (Manage Server required)",
    )
    @app_commands.describe(
        member="Member who should receive XP",
        amount="XP amount to grant (1–1,000,000)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def give_xp(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                "Bots cannot earn XP.", ephemeral=True
            )
            return

        redis = self.bot.state.redis
        key = xp_key(interaction.guild.id)
        previous_xp = int((await redis.zscore(key, str(member.id))) or 0)
        old_level = level_from_xp(previous_xp)
        new_total = await redis.zincrby(key, int(amount), str(member.id))
        new_total = int(new_total)
        new_level = level_from_xp(new_total)

        await interaction.response.send_message(
            f"Granted **{amount:,} XP** to {member.mention}. "
            f"They are now level **{new_level}** ({new_total:,} XP)."
        )

        if new_level > old_level:
            await self.handle_level_up(
                member,
                new_level,
                interaction.channel,
            )

    @give_xp.error
    async def give_xp_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "You need Manage Server to use /give-xp."
        else:
            message = "Could not grant XP."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="leaderboard", description="Show the server XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        redis = self.bot.state.redis
        entries = await redis.zrevrange(
            xp_key(interaction.guild.id),
            0,
            9,
            withscores=True,
        )

        if not entries:
            await interaction.response.send_message(
                "Nobody has earned XP yet. Start chatting!"
            )
            return

        lines: list[str] = []

        for index, (user_id, score) in enumerate(entries, start=1):
            xp = int(score)
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"
            lines.append(
                f"**{index}.** {name} — Level {level_from_xp(xp)} ({xp:,} XP)"
            )

        embed = discord.Embed(
            title=f"XP Leaderboard — {interaction.guild.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )

        await interaction.response.send_message(embed=embed)
