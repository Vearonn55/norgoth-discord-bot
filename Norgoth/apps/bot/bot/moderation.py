"""Moderation slash commands with audit logging."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.moderation")

MAX_PURGE_MESSAGES = 100
MAX_TIMEOUT_MINUTES = 60 * 24 * 28  # Discord's 28-day cap


class ModerationCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True

        enabled = await self.bot.state.is_module_enabled(
            interaction.guild.id, "moderation"
        )

        if not enabled:
            await interaction.response.send_message(
                "The moderation module is disabled in the Norgoth dashboard.",
                ephemeral=True,
            )

        return enabled

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

        # Mirror into config-driven logging (Postgres-backed routing snapshot).
        mod_event_types = {
            "kick": "mod_kick",
            "ban": "mod_ban",
            "timeout": "mod_timeout",
            "purge": "mod_purge",
            "warn": "mod_warn",
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
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.exception("Failed to post moderation embed")

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick", reason="Why they are being kicked")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
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
        )

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.describe(user="User to ban", reason="Why they are being banned")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
    ) -> None:
        assert interaction.guild is not None

        try:
            await interaction.guild.ban(user, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to ban that user.",
                ephemeral=True,
            )
            return

        await self.log_action(interaction, "ban", f"{user} ({user.id})", reason)
        await interaction.response.send_message(
            f"Banned {user.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="timeout",
        description="Timeout a member for a number of minutes.",
    )
    @app_commands.describe(
        member="Member to timeout",
        minutes="Timeout duration in minutes (max 28 days)",
        reason="Why they are being timed out",
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, MAX_TIMEOUT_MINUTES],
        reason: str | None = None,
    ) -> None:
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
        )

    @app_commands.command(
        name="purge",
        description="Delete the last N messages in this channel.",
    )
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
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

    @app_commands.command(name="userinfo", description="Show info about a member.")
    @app_commands.describe(member="Member to inspect (defaults to you)")
    @app_commands.guild_only()
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        assert isinstance(target, discord.Member)

        embed = discord.Embed(
            title=f"{target}",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="ID", value=str(target.id), inline=True)
        embed.add_field(
            name="Account created",
            value=discord.utils.format_dt(target.created_at, style="R"),
            inline=True,
        )

        if target.joined_at:
            embed.add_field(
                name="Joined server",
                value=discord.utils.format_dt(target.joined_at, style="R"),
                inline=True,
            )

        roles = [role.mention for role in target.roles if not role.is_default()]
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles) if roles else "None",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
