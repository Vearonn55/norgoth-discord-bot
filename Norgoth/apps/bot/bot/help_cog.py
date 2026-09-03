"""Discovery commands: /help, /dashboard, /status."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from bot.commands.i18n import L
from bot.commands.registry import CommandSpec, command_by_name, commands_for_help

if TYPE_CHECKING:
    from bot.client import NorgothBot


def _member_has_defaults(member: discord.Member, spec: CommandSpec) -> bool:
    if not spec.default_member_permissions:
        return True
    if member.guild.owner_id == member.id:
        return True
    perms = member.guild_permissions
    for name in spec.default_member_permissions:
        if not getattr(perms, name, False):
            return False
    return True


class HelpCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    def _dashboard_origin(self) -> str:
        return (
            self.bot.settings.dashboard_url
            or os.getenv("NORGOTH_DASHBOARD_URL", "").strip()
            or os.getenv("NEXT_PUBLIC_DASHBOARD_URL", "").strip()
            or "https://www.norbot.io"
        ).rstrip("/")

    async def _help_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        needle = current.lower().strip()
        choices: list[app_commands.Choice[str]] = []
        for spec in commands_for_help():
            if needle and needle not in spec.name.lower():
                continue
            choices.append(
                app_commands.Choice(name=spec.name, value=spec.name)
            )
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="help", description=L("cmd.help.description"))
    @app_commands.describe(command="Optional command name for details")
    @app_commands.autocomplete(command=_help_autocomplete)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def help_command(
        self,
        interaction: discord.Interaction,
        command: str | None = None,
    ) -> None:
        assert interaction.guild is not None

        if command:
            spec = command_by_name(command)
            if spec is None or spec.command_type != "chat":
                await interaction.response.send_message(
                    f"Unknown command `{command}`.",
                    ephemeral=True,
                )
                return
            embed = discord.Embed(
                title=f"/{spec.name}",
                description=spec.description,
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Category", value=spec.category, inline=True)
            if spec.module:
                embed.add_field(name="Module", value=spec.module, inline=True)
            if spec.options:
                embed.add_field(
                    name="Options",
                    value=", ".join(spec.options),
                    inline=False,
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        member = (
            interaction.user
            if isinstance(interaction.user, discord.Member)
            else None
        )
        enabled_modules: dict[str, bool] = {}
        grouped: dict[str, list[str]] = {}

        for spec in commands_for_help():
            if member is not None and not _member_has_defaults(member, spec):
                continue
            if spec.module:
                if spec.module not in enabled_modules:
                    enabled_modules[spec.module] = await self.bot.state.is_module_enabled(
                        interaction.guild.id, spec.module
                    )
                if not enabled_modules[spec.module]:
                    continue
            grouped.setdefault(spec.category, []).append(f"`/{spec.name}`")

        embed = discord.Embed(
            title="NorBot commands",
            description=(
                "Commands you can use here. Open the dashboard for full config."
            ),
            color=discord.Color.blurple(),
        )
        for category in (
            "General",
            "Info",
            "Levels",
            "Moderation",
            "Tickets",
            "Invites",
            "Verification",
            "Campaigns",
        ):
            lines = grouped.get(category)
            if not lines:
                continue
            embed.add_field(
                name=category,
                value=" ".join(lines)[:1024],
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="dashboard", description=L("cmd.dashboard.description")
    )
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def dashboard(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        url = f"{self._dashboard_origin()}/servers/{interaction.guild.id}"
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Open dashboard",
                style=discord.ButtonStyle.link,
                url=url,
            )
        )
        await interaction.response.send_message(
            f"Manage **{interaction.guild.name}** in the NorBot dashboard.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="status", description=L("cmd.status.description"))
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        latency_ms = round(self.bot.latency * 1000)
        guild_count = len(self.bot.guilds)
        workers_ok: str | None = None
        base = self.bot.settings.api_base_url.rstrip("/")
        if base:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{base}/health")
                    if response.status_code == 200:
                        workers_ok = "API healthy"
                    else:
                        workers_ok = f"API HTTP {response.status_code}"
            except Exception:  # noqa: BLE001
                workers_ok = "API unreachable"

        embed = discord.Embed(
            title="NorBot status",
            color=discord.Color.green(),
        )
        embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=True)
        embed.add_field(name="Guilds", value=str(guild_count), inline=True)
        embed.add_field(
            name="Sync mode",
            value=self.bot.settings.command_sync_mode,
            inline=True,
        )
        if workers_ok:
            embed.add_field(name="API", value=workers_ok, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
