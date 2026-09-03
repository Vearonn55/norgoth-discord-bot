"""Info commands: /userinfo, /avatar, /server, /roles (+ User info context)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands.i18n import L

if TYPE_CHECKING:
    from bot.client import NorgothBot


class InfoCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot
        self.ctx_userinfo = app_commands.ContextMenu(
            name=L("ctx.userinfo"),
            callback=self.context_userinfo,
        )
        self.bot.tree.add_command(self.ctx_userinfo)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.ctx_userinfo.name, type=self.ctx_userinfo.type
        )

    async def _send_userinfo(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        *,
        ephemeral: bool = True,
    ) -> None:
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

        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="userinfo", description=L("cmd.userinfo.description"))
    @app_commands.describe(member="Member to inspect (defaults to you)")
    @app_commands.checks.cooldown(1, 3.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        assert isinstance(target, discord.Member)
        await self._send_userinfo(interaction, target, ephemeral=True)

    @app_commands.guild_only()
    async def context_userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        await self._send_userinfo(interaction, member, ephemeral=True)

    @app_commands.command(name="avatar", description=L("cmd.avatar.description"))
    @app_commands.describe(
        user="User to show (defaults to you)",
        type="Which avatar to show",
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Display", value="display"),
            app_commands.Choice(name="Server", value="server"),
        ]
    )
    @app_commands.checks.cooldown(1, 3.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def avatar(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        type: app_commands.Choice[str] | None = None,
    ) -> None:
        target = user or interaction.user
        assert isinstance(target, discord.Member)
        kind = type.value if type is not None else "display"
        if kind == "server" and target.guild_avatar is not None:
            asset = target.guild_avatar
            label = "Server avatar"
        else:
            asset = target.avatar or target.default_avatar
            label = "Display avatar"

        embed = discord.Embed(
            title=f"{label} — {target.display_name}",
            color=discord.Color.blurple(),
        )
        embed.set_image(url=asset.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server", description=L("cmd.server.description"))
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def server(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        assert guild is not None

        embed = discord.Embed(
            title=guild.name,
            color=discord.Color.blurple(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(guild.created_at, style="R"),
            inline=True,
        )
        embed.add_field(
            name="Channels",
            value=str(len(guild.channels)),
            inline=True,
        )
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        owner = guild.owner
        if owner is not None:
            embed.add_field(name="Owner", value=str(owner), inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roles", description=L("cmd.roles.description"))
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def roles_list(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        assert guild is not None

        roles = [
            role
            for role in sorted(guild.roles, key=lambda r: r.position, reverse=True)
            if not role.is_default()
        ]
        if not roles:
            await interaction.response.send_message(
                "This server has no roles besides @everyone.",
                ephemeral=True,
            )
            return

        lines = [f"{role.mention} — `{role.id}`" for role in roles]
        # Discord embed description limit 4096; keep ephemeral pages thin.
        chunks: list[str] = []
        current = ""
        for line in lines:
            addition = line if not current else f"{current}\n{line}"
            if len(addition) > 3900:
                chunks.append(current)
                current = line
            else:
                current = addition
        if current:
            chunks.append(current)

        embeds = [
            discord.Embed(
                title=f"Roles ({len(roles)})",
                description=chunk,
                color=discord.Color.blurple(),
            )
            for chunk in chunks[:5]
        ]
        await interaction.response.send_message(embeds=embeds, ephemeral=True)
