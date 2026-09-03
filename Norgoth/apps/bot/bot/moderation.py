"""Moderation slash commands, context menus, and audit logging."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from bot.commands.checks import (
    NO_MENTIONS,
    ensure_member_hierarchy,
    module_enabled,
    truncate_reason,
)
from bot.commands.errors import HierarchyError
from bot.commands.i18n import L
from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.moderation")

MAX_PURGE_MESSAGES = 100
MAX_TIMEOUT_MINUTES = 60 * 24 * 28  # Discord's 28-day cap
MAX_SLOWMODE_SECONDS = 21_600
SNOWFLAKE_RE = re.compile(r"^\d{5,25}$")
CTX_TIMEOUT_MINUTES = 10


class ModerationCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        self.ctx_kick = app_commands.ContextMenu(
            name=L("ctx.kick"),
            callback=self.context_kick,
        )
        self.ctx_ban = app_commands.ContextMenu(
            name=L("ctx.ban"),
            callback=self.context_ban,
        )
        self.ctx_timeout = app_commands.ContextMenu(
            name=L("ctx.timeout"),
            callback=self.context_timeout,
        )
        self.bot.tree.add_command(self.ctx_kick)
        self.bot.tree.add_command(self.ctx_ban)
        self.bot.tree.add_command(self.ctx_timeout)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_kick.name, type=self.ctx_kick.type)
        self.bot.tree.remove_command(self.ctx_ban.name, type=self.ctx_ban.type)
        self.bot.tree.remove_command(
            self.ctx_timeout.name, type=self.ctx_timeout.type
        )

    async def log_action(
        self,
        interaction: discord.Interaction,
        action: str,
        target: str,
        reason: str | None,
        detail: str | None = None,
    ) -> None:
        assert interaction.guild is not None

        entry = {
            "action": action,
            "moderator_id": str(interaction.user.id),
            "moderator_name": str(interaction.user),
            "target": target,
            "reason": reason or "No reason provided",
            "detail": detail,
            "created_at": now_iso(),
        }

        try:
            await self.bot.state.append_moderation_log(interaction.guild.id, entry)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist moderation log entry")

        mod_event_types = {
            "kick": "mod_kick",
            "ban": "mod_ban",
            "unban": "mod_ban",
            "timeout": "mod_timeout",
            "untimeout": "mod_timeout",
            "purge": "mod_purge",
            "warn": "mod_warn",
            "setnick": "mod_kick",
            "vkick": "mod_kick",
            "move": "mod_kick",
            "lock": "mod_purge",
            "unlock": "mod_purge",
            "slowmode": "mod_purge",
        }
        logging_cog = self.bot.get_cog("ServerLoggingCog")
        if logging_cog is not None and action in mod_event_types:
            fields = {
                "Target": target,
                "Moderator": str(interaction.user),
                "Reason": entry["reason"],
            }
            if detail:
                fields["Detail"] = detail
            await logging_cog.log_moderation(
                interaction.guild,
                mod_event_types[action],
                f"Moderation: {action}",
                f"{interaction.user} used /{action} on {target}.",
                fields,
                actor_name=str(interaction.user),
            )

        config = await self.bot.state.get_automation_config(interaction.guild.id)
        log_channel_id = config.get("mod_log_channel_id")

        if not log_channel_id:
            return

        channel = interaction.guild.get_channel(int(log_channel_id))

        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title=f"Moderation: {action}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Target", value=target, inline=True)
        embed.add_field(name="Moderator", value=str(interaction.user), inline=True)
        embed.add_field(name="Reason", value=entry["reason"], inline=False)

        if detail:
            embed.add_field(name="Detail", value=detail, inline=False)

        try:
            await channel.send(embed=embed, allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            logger.exception("Failed to post moderation embed")

    async def _ingest_guild_ban(
        self,
        guild_id: int,
        user: discord.User | discord.Member,
        *,
        is_active: bool,
        source: str,
    ) -> None:
        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if not base or not token:
            return
        payload = {
            "discord_user_id": str(user.id),
            "is_active": is_active,
            "username": getattr(user, "name", None) or str(user),
            "display_name": getattr(user, "global_name", None),
            "source": source,
            "created_at": now_iso(),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{base}/internal/ingest/{guild_id}/guild-ban",
                    headers={
                        "X-Norgoth-Internal-Token": token,
                        "X-Norgoth-Bot-Token": token,
                    },
                    json=payload,
                )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Guild ban ingest failed guild_id=%s user_id=%s",
                guild_id,
                user.id,
                exc_info=True,
            )

    async def _resolve_user_ref(
        self,
        interaction: discord.Interaction,
        user: str,
    ) -> discord.User | None:
        assert interaction.guild is not None
        raw = user.strip()
        mention = re.fullmatch(r"<@!?(\d{5,25})>", raw)
        snowflake = mention.group(1) if mention else raw
        if not SNOWFLAKE_RE.fullmatch(snowflake):
            return None
        user_id = int(snowflake)
        member = interaction.guild.get_member(user_id)
        if member is not None:
            return member
        cached = self.bot.get_user(user_id)
        if cached is not None:
            return cached
        try:
            return await self.bot.fetch_user(user_id)
        except discord.HTTPException:
            return None

    @app_commands.command(name="kick", description=L("cmd.kick.description"))
    @app_commands.describe(member="Member to kick", reason="Why they are being kicked")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
        reason = truncate_reason(reason)
        try:
            await ensure_member_hierarchy(interaction, member)
        except HierarchyError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to kick that member.",
                ephemeral=True,
            )
            return

        await self.log_action(interaction, "kick", f"{member} ({member.id})", reason)
        await interaction.response.send_message(
            f"Kicked {member.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="ban", description=L("cmd.ban.description"))
    @app_commands.describe(user="User to ban", reason="Why they are being banned")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
    ) -> None:
        assert interaction.guild is not None
        reason = truncate_reason(reason)

        member = interaction.guild.get_member(user.id)
        if member is not None:
            try:
                await ensure_member_hierarchy(interaction, member)
            except HierarchyError as exc:
                await interaction.response.send_message(exc.message, ephemeral=True)
                return

        try:
            await interaction.guild.ban(user, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to ban that user.",
                ephemeral=True,
            )
            return

        await self.log_action(interaction, "ban", f"{user} ({user.id})", reason)
        await self._ingest_guild_ban(
            interaction.guild.id,
            user,
            is_active=True,
            source="slash_ban",
        )
        await interaction.response.send_message(
            f"Banned {user.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="timeout", description=L("cmd.timeout.description"))
    @app_commands.describe(
        member="Member to timeout",
        minutes="Timeout duration in minutes (max 28 days)",
        reason="Why they are being timed out",
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, MAX_TIMEOUT_MINUTES],
        reason: str | None = None,
    ) -> None:
        reason = truncate_reason(reason)
        try:
            await ensure_member_hierarchy(interaction, member)
        except HierarchyError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        try:
            await member.timeout(timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to timeout that member.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction,
            "timeout",
            f"{member} ({member.id})",
            reason,
            detail=f"{minutes} minutes",
        )
        await interaction.response.send_message(
            f"Timed out {member.mention} for {minutes} minutes.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="purge", description=L("cmd.purge.description"))
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, MAX_PURGE_MESSAGES],
    ) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Purge only works in text channels.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)

        await self.log_action(
            interaction,
            "purge",
            f"#{interaction.channel.name}",
            None,
            detail=f"{len(deleted)} messages deleted",
        )
        await interaction.followup.send(
            f"Deleted {len(deleted)} messages.",
            ephemeral=True,
        )

    @app_commands.command(name="unban", description=L("cmd.unban.description"))
    @app_commands.describe(
        user="User ID or mention to unban",
        reason="Why the ban is being removed",
    )
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def unban(
        self,
        interaction: discord.Interaction,
        user: str,
        reason: str | None = None,
    ) -> None:
        assert interaction.guild is not None
        reason = truncate_reason(reason)
        target = await self._resolve_user_ref(interaction, user)
        if target is None:
            await interaction.response.send_message(
                "Provide a valid user ID or mention.",
                ephemeral=True,
            )
            return

        try:
            await interaction.guild.unban(target, reason=reason)
        except discord.NotFound:
            await interaction.response.send_message(
                "That user is not banned.",
                ephemeral=True,
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to unban that user.",
                ephemeral=True,
            )
            return

        await self.log_action(interaction, "unban", f"{target} ({target.id})", reason)
        await self._ingest_guild_ban(
            interaction.guild.id,
            target,
            is_active=False,
            source="slash_unban",
        )
        await interaction.response.send_message(
            f"Unbanned {target}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="untimeout", description=L("cmd.untimeout.description"))
    @app_commands.describe(member="Member to remove timeout from", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
        reason = truncate_reason(reason)
        try:
            await ensure_member_hierarchy(interaction, member)
        except HierarchyError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        try:
            await member.timeout(None, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to remove that timeout.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction, "untimeout", f"{member} ({member.id})", reason
        )
        await interaction.response.send_message(
            f"Removed timeout from {member.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="setnick", description=L("cmd.setnick.description"))
    @app_commands.describe(
        member="Member to rename",
        nickname="New nickname (omit to clear)",
    )
    @app_commands.default_permissions(manage_nicknames=True)
    @app_commands.checks.bot_has_permissions(manage_nicknames=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def setnick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str | None = None,
    ) -> None:
        try:
            await ensure_member_hierarchy(interaction, member)
        except HierarchyError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        nick = truncate_reason(nickname, limit=32)
        try:
            await member.edit(nick=nick, reason=f"/setnick by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to change that nickname.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction,
            "setnick",
            f"{member} ({member.id})",
            None,
            detail=nick or "(cleared)",
        )
        await interaction.response.send_message(
            f"Updated nickname for {member.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="vkick", description=L("cmd.vkick.description"))
    @app_commands.describe(member="Member to disconnect from voice", reason="Reason")
    @app_commands.default_permissions(move_members=True)
    @app_commands.checks.bot_has_permissions(move_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def vkick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
        reason = truncate_reason(reason)
        try:
            await ensure_member_hierarchy(interaction, member)
        except HierarchyError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        if member.voice is None or member.voice.channel is None:
            await interaction.response.send_message(
                "That member is not in a voice channel.",
                ephemeral=True,
            )
            return

        try:
            await member.move_to(None, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to disconnect that member.",
                ephemeral=True,
            )
            return

        await self.log_action(interaction, "vkick", f"{member} ({member.id})", reason)
        await interaction.response.send_message(
            f"Disconnected {member.mention} from voice.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="move", description=L("cmd.move.description"))
    @app_commands.describe(
        member="Member to move",
        channel="Destination voice channel",
    )
    @app_commands.default_permissions(move_members=True)
    @app_commands.checks.bot_has_permissions(move_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def move(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        channel: discord.VoiceChannel,
    ) -> None:
        try:
            await ensure_member_hierarchy(interaction, member)
        except HierarchyError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        if member.voice is None or member.voice.channel is None:
            await interaction.response.send_message(
                "That member is not in a voice channel.",
                ephemeral=True,
            )
            return

        try:
            await member.move_to(channel, reason=f"/move by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to move that member.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction,
            "move",
            f"{member} ({member.id})",
            None,
            detail=f"→ #{channel.name}",
        )
        await interaction.response.send_message(
            f"Moved {member.mention} to {channel.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="lock", description=L("cmd.lock.description"))
    @app_commands.describe(channel="Channel to lock (defaults to current)", reason="Reason")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def lock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        reason: str | None = None,
    ) -> None:
        assert interaction.guild is not None
        reason = truncate_reason(reason)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                "Lock only works on text channels.",
                ephemeral=True,
            )
            return

        overwrite = target.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        try:
            await target.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=reason or f"/lock by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to lock that channel.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction, "lock", f"#{target.name}", reason
        )
        await interaction.response.send_message(
            f"Locked {target.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="unlock", description=L("cmd.unlock.description"))
    @app_commands.describe(
        channel="Channel to unlock (defaults to current)",
        reason="Reason",
    )
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        reason: str | None = None,
    ) -> None:
        assert interaction.guild is not None
        reason = truncate_reason(reason)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                "Unlock only works on text channels.",
                ephemeral=True,
            )
            return

        overwrite = target.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        try:
            await target.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=reason or f"/unlock by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to unlock that channel.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction, "unlock", f"#{target.name}", reason
        )
        await interaction.response.send_message(
            f"Unlocked {target.mention}.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="slowmode", description=L("cmd.slowmode.description"))
    @app_commands.describe(
        seconds="Slowmode delay in seconds (0 to disable)",
        channel="Channel to update (defaults to current)",
    )
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, MAX_SLOWMODE_SECONDS],
        channel: discord.TextChannel | None = None,
    ) -> None:
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                "Slowmode only works on text channels.",
                ephemeral=True,
            )
            return

        try:
            await target.edit(
                slowmode_delay=seconds,
                reason=f"/slowmode by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to edit that channel.",
                ephemeral=True,
            )
            return

        await self.log_action(
            interaction,
            "slowmode",
            f"#{target.name}",
            None,
            detail=f"{seconds}s",
        )
        await interaction.response.send_message(
            f"Set slowmode in {target.mention} to **{seconds}** seconds.",
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @app_commands.command(name="modlogs", description=L("cmd.modlogs.description"))
    @app_commands.describe(limit="How many recent entries to show (1–25)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def modlogs(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        assert interaction.guild is not None
        entries = await self.bot.state.get_moderation_logs(
            interaction.guild.id, limit=limit
        )
        if not entries:
            await interaction.response.send_message(
                "No recent moderation actions recorded.",
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for entry in entries:
            action = str(entry.get("action") or "?")
            target = str(entry.get("target") or "unknown")
            moderator = str(entry.get("moderator_name") or "unknown")
            reason = str(entry.get("reason") or "")
            # Privacy: never include IP/evidence-like fields if present.
            detail = entry.get("detail")
            line = f"**{action}** → {target} by {moderator}"
            if reason and reason != "No reason provided":
                line += f" — {reason[:80]}"
            if detail:
                line += f" ({str(detail)[:60]})"
            lines.append(line)

        embed = discord.Embed(
            title="Recent moderation",
            description="\n".join(lines)[:4000],
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- context menus ------------------------------------------------------

    @app_commands.default_permissions(kick_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def context_kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        await self.kick.callback(self, interaction, member, None)

    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def context_ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        await self.ban.callback(self, interaction, user, None)

    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    @module_enabled("moderation")
    async def context_timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        await self.timeout.callback(
            self, interaction, member, CTX_TIMEOUT_MINUTES, "Context menu timeout"
        )
