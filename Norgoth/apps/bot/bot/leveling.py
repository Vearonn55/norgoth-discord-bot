"""Level & activity system: XP per message, level-ups, and role rewards."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
import httpx
from discord import app_commands
from discord.ext import commands, tasks

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

# Voice Chat XP. Bounds must stay in sync with LevelingConfig in
# apps/api/app/routes/leveling.py and the dashboard store. A value of 0 means
# voice XP is disabled (there is no separate enable flag).
VOICE_XP_PER_MINUTE_MIN = 0
VOICE_XP_PER_MINUTE_MAX = 100
DEFAULT_VOICE_XP_PER_MINUTE = 0
# Voice XP accrues once per this interval ("XP per minute in voice").
VOICE_XP_INTERVAL_SECONDS = 60

DEFAULT_CONFIG: dict[str, Any] = {
    "announce_mode": "current",  # "current" | "channel" | "off"
    "announce_channel_id": None,
    "xp_per_message": DEFAULT_XP_PER_MESSAGE,
    "xp_multiplier": DEFAULT_XP_MULTIPLIER,
    # Keep in sync with DEFAULT_LEVEL_THRESHOLD_SCALE (defined below); a literal
    # is used here because this dict is evaluated before that constant.
    "level_threshold_scale": 1.0,
    "level_up_message": "🎉 {user} reached level **{level}**!",
    "level_up_embed": {},
    "reward_roles": [],  # [{"level": 5, "role_id": "..."}]
    "voice_xp_per_minute": DEFAULT_VOICE_XP_PER_MINUTE,
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


def effective_voice_xp(config: dict[str, Any]) -> int:
    """Compute XP awarded per minute of eligible voice participation.

    Mirrors :func:`effective_xp`: ``effective = voice_xp_per_minute * multiplier``
    (rounded, minimum 1). The same global multiplier scales both message and
    voice XP; eligibility (who counts) is enforced separately by the loop.
    """

    try:
        base = int(config.get("voice_xp_per_minute", DEFAULT_VOICE_XP_PER_MINUTE))
    except (TypeError, ValueError):
        base = DEFAULT_VOICE_XP_PER_MINUTE
    base = max(VOICE_XP_PER_MINUTE_MIN, min(VOICE_XP_PER_MINUTE_MAX, base))

    # A per-minute value of 0 disables voice XP; award nothing.
    if base <= 0:
        return 0

    try:
        multiplier = float(config.get("xp_multiplier", DEFAULT_XP_MULTIPLIER))
    except (TypeError, ValueError):
        multiplier = DEFAULT_XP_MULTIPLIER
    multiplier = max(XP_MULTIPLIER_MIN, min(XP_MULTIPLIER_MAX, multiplier))

    return max(1, round(base * multiplier))


def leveling_config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:leveling:config"


def xp_key(guild_id: int | str) -> str:
    """Total XP (text + voice) — drives levels and /rank."""

    return f"norgoth:guild:{guild_id}:xp"


def xp_text_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:xp:text"


def xp_voice_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:xp:voice"


def xp_cooldown_key(guild_id: int | str, user_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:xp:cooldown:{user_id}"


LEVEL_THRESHOLD_SCALE_MIN = 0.5
LEVEL_THRESHOLD_SCALE_MAX = 2.0
DEFAULT_LEVEL_THRESHOLD_SCALE = 1.0


def threshold_scale(config: dict[str, Any]) -> float:
    """Read + clamp the guild's level-up curve scale (fail-safe to default)."""

    try:
        value = float(config.get("level_threshold_scale", DEFAULT_LEVEL_THRESHOLD_SCALE))
    except (TypeError, ValueError):
        return DEFAULT_LEVEL_THRESHOLD_SCALE
    return max(LEVEL_THRESHOLD_SCALE_MIN, min(LEVEL_THRESHOLD_SCALE_MAX, value))


def xp_for_level(level: int, scale: float = DEFAULT_LEVEL_THRESHOLD_SCALE) -> int:
    """Total XP required to reach a level (cumulative, MEE6-style curve).

    ``scale`` stretches (>1) or compresses (<1) the curve. Stored XP is never
    rewritten, so a scale change re-derives levels live.
    """

    scale = max(LEVEL_THRESHOLD_SCALE_MIN, min(LEVEL_THRESHOLD_SCALE_MAX, scale))
    total = 0
    for step in range(level):
        total += 5 * step**2 + 50 * step + 100
    return int(round(total * scale))


def level_from_xp(xp: int, scale: float = DEFAULT_LEVEL_THRESHOLD_SCALE) -> int:
    scale = max(LEVEL_THRESHOLD_SCALE_MIN, min(LEVEL_THRESHOLD_SCALE_MAX, scale))
    level = 0
    while xp >= xp_for_level(level + 1, scale):
        level += 1
    return level


class LevelingCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.voice_xp_loop.start()

    def cog_unload(self) -> None:
        self.voice_xp_loop.cancel()

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(leveling_config_key(guild_id))
        config = {**DEFAULT_CONFIG, **stored}
        # Legacy migration: older configs gated voice XP with a boolean. When it
        # was explicitly off, treat the per-minute value as 0 (disabled). The
        # numeric value is now the single source of truth.
        if config.get("voice_xp_enabled") is False:
            config["voice_xp_per_minute"] = 0
        config.pop("voice_xp_enabled", None)
        return config

    async def _seed_text_xp_from_total(
        self, guild_id: int, user_id: int | str
    ) -> None:
        """One-time heal: pre-split totals lived only on ``:xp``; attribute to text."""

        redis = self.bot.state.redis
        member = str(user_id)
        if await redis.zscore(xp_text_key(guild_id), member) is not None:
            return
        total = await redis.zscore(xp_key(guild_id), member)
        if total is not None and float(total) > 0:
            await redis.zadd(xp_text_key(guild_id), {member: float(total)})

    async def _award_metric_xp(
        self,
        guild_id: int,
        user_id: int | str,
        gain: int,
        *,
        metric: str,
    ) -> tuple[int, int]:
        """Increment metric + total ZSETs. Returns (previous_total, new_total)."""

        redis = self.bot.state.redis
        member = str(user_id)
        # Always heal text from legacy totals before any award/ingest so voice
        # awards cannot POST text_xp=0 and wipe Postgres.
        await self._seed_text_xp_from_total(guild_id, member)
        metric_key = (
            xp_text_key(guild_id) if metric == "text" else xp_voice_key(guild_id)
        )

        previous_total = int(await redis.zscore(xp_key(guild_id), member) or 0)
        await redis.zincrby(metric_key, gain, member)
        new_total = int(await redis.zincrby(xp_key(guild_id), gain, member))
        await self._ingest_xp_rollup(guild_id, member)
        return previous_total, new_total

    async def _ingest_xp_rollup(self, guild_id: int, user_id: str) -> None:
        """Best-effort dual-write of absolute XP totals to Postgres via ingest."""

        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if not base or not token:
            return

        redis = self.bot.state.redis
        await self._seed_text_xp_from_total(guild_id, user_id)
        text_xp = int(await redis.zscore(xp_text_key(guild_id), user_id) or 0)
        voice_xp = int(await redis.zscore(xp_voice_key(guild_id), user_id) or 0)
        total = int(await redis.zscore(xp_key(guild_id), user_id) or 0)
        # If text ZSET was still empty somehow, derive from total − voice.
        if text_xp <= 0 and total > voice_xp:
            text_xp = max(0, total - voice_xp)
            if text_xp > 0:
                await redis.zadd(xp_text_key(guild_id), {user_id: float(text_xp)})

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{base}/internal/ingest/{guild_id}/xp",
                    headers={
                        "X-Norgoth-Internal-Token": token,
                        "X-Norgoth-Bot-Token": token,
                    },
                    json={
                        "user_id": user_id,
                        "text_xp": text_xp,
                        "voice_xp": voice_xp,
                    },
                )
        except Exception:  # noqa: BLE001 - never block awards on ingest failure
            logger.debug(
                "XP ingest failed for guild %s user %s", guild_id, user_id, exc_info=True
            )

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

        gain = effective_xp(config)
        previous_xp, new_xp = await self._award_metric_xp(
            guild.id, message.author.id, gain, metric="text"
        )

        scale = threshold_scale(config)
        old_level = level_from_xp(previous_xp, scale)
        new_level = level_from_xp(new_xp, scale)

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

    # ---- voice XP ------------------------------------------------------------

    @staticmethod
    def _voice_member_eligible(member: discord.Member) -> bool:
        """Return whether a member's current voice state earns XP.

        Policy ("meaningful participation, not idle farming"):
        - bots never earn (filtered by the caller before this check);
        - AFK-channel members never earn (filtered by the caller);
        - self-deafened, server-deafened, and server-muted members are excluded
          (they cannot meaningfully participate / are being moderated);
        - self-muted members STILL earn, since listening is participation.
        """

        voice = member.voice
        if voice is None:
            return False
        if voice.self_deaf or voice.deaf or voice.mute:
            return False
        return True

    async def _award_voice_xp_for_guild(self, guild: discord.Guild) -> None:
        if not await self.bot.state.is_module_enabled(guild.id, "leveling"):
            return

        config = await self.get_config(guild.id)
        gain = effective_voice_xp(config)
        # 0 per-minute (the disabled state) means no voice XP is awarded.
        if gain <= 0:
            return

        scale = threshold_scale(config)
        afk_channel_id = guild.afk_channel.id if guild.afk_channel else None
        redis = self.bot.state.redis

        for channel in guild.voice_channels:
            # AFK channel participation never earns XP.
            if afk_channel_id is not None and channel.id == afk_channel_id:
                continue

            # Require at least two non-bot humans so a user alone in a channel
            # cannot idle-farm XP.
            humans = [member for member in channel.members if not member.bot]
            if len(humans) < 2:
                continue

            for member in humans:
                if not self._voice_member_eligible(member):
                    continue

                previous_xp, new_xp = await self._award_metric_xp(
                    guild.id, member.id, gain, metric="voice"
                )

                old_level = level_from_xp(previous_xp, scale)
                new_level = level_from_xp(new_xp, scale)
                if new_level > old_level:
                    await self.handle_level_up(member, new_level, None)

    @tasks.loop(seconds=VOICE_XP_INTERVAL_SECONDS)
    async def voice_xp_loop(self) -> None:
        """Award voice XP once per minute to eligible members in every guild."""

        for guild in list(self.bot.guilds):
            try:
                await self._award_voice_xp_for_guild(guild)
            except Exception:  # noqa: BLE001 - never let one guild break the loop
                logger.exception("Voice XP loop failed for guild %s", guild.id)

    @voice_xp_loop.before_loop
    async def before_voice_xp_loop(self) -> None:
        await self.bot.wait_until_ready()

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
        scale = threshold_scale(await self.get_config(interaction.guild.id))
        level = level_from_xp(xp, scale)
        rank = await redis.zrevrank(key, str(target.id))

        current_floor = xp_for_level(level, scale)
        next_requirement = xp_for_level(level + 1, scale)

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

        # Respect the leveling master switch: when disabled, XP progression is
        # halted for the guild, including manual grants.
        if not await self.bot.state.is_module_enabled(
            interaction.guild.id, "leveling"
        ):
            await interaction.response.send_message(
                "Leveling is disabled for this server.", ephemeral=True
            )
            return

        scale = threshold_scale(await self.get_config(interaction.guild.id))
        previous_xp, new_total = await self._award_metric_xp(
            interaction.guild.id, member.id, int(amount), metric="text"
        )
        old_level = level_from_xp(previous_xp, scale)
        new_level = level_from_xp(new_total, scale)

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
    @app_commands.describe(type="Leaderboard metric (text or voice XP)")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Text XP", value="text"),
            app_commands.Choice(name="Voice XP", value="voice"),
        ]
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        type: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        metric = (type.value if type else "text")
        redis = self.bot.state.redis
        key = (
            xp_text_key(interaction.guild.id)
            if metric == "text"
            else xp_voice_key(interaction.guild.id)
        )
        if metric == "text":
            # Heal empty text ZSET from pre-split totals for top members.
            total_entries = await redis.zrevrange(
                xp_key(interaction.guild.id), 0, 9, withscores=True
            )
            for user_id, score in total_entries:
                await self._seed_text_xp_from_total(interaction.guild.id, user_id)

        entries = await redis.zrevrange(key, 0, 9, withscores=True)

        if not entries:
            label = "Text" if metric == "text" else "Voice"
            await interaction.response.send_message(
                f"Nobody has earned {label} XP yet."
            )
            return

        scale = threshold_scale(await self.get_config(interaction.guild.id))
        lines: list[str] = []
        label = "Text XP" if metric == "text" else "Voice XP"

        for index, (user_id, score) in enumerate(entries, start=1):
            xp = int(score)
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"
            lines.append(
                f"**{index}.** {name} — {xp:,} {label} "
                f"(Level {level_from_xp(xp, scale)})"
            )

        embed = discord.Embed(
            title=f"{label} Leaderboard — {interaction.guild.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )

        await interaction.response.send_message(embed=embed)
