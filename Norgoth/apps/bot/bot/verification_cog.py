"""Verification slash helpers (dashboard deep-link only; no approve/reject)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from bot.commands.i18n import L

if TYPE_CHECKING:
    from bot.client import NorgothBot


class VerificationCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    verification_group = app_commands.Group(
        name="verification",
        description=L("cmd.verification.description"),
        default_permissions=discord.Permissions(manage_roles=True),
        guild_only=True,
    )

    @verification_group.command(
        name="pending",
        description=L("cmd.verification.pending.description"),
    )
    async def verification_pending(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None

        count: int | None = None
        base = getattr(self.bot.state, "_api_base_url", "") or ""
        token = getattr(self.bot.state, "_bot_token", "") or ""
        if base and token:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{base}/internal/ingest/{interaction.guild.id}/verification-pending-count",
                        headers={
                            "X-Norgoth-Internal-Token": token,
                            "X-Norgoth-Bot-Token": token,
                        },
                    )
                    if response.status_code == 200:
                        payload = response.json()
                        if isinstance(payload, dict) and "count" in payload:
                            count = int(payload["count"])
            except Exception:  # noqa: BLE001
                count = None

        origin = self.bot.settings.dashboard_url.rstrip("/")
        url = (
            f"{origin}/servers/{interaction.guild.id}"
            "/community/manual-verification"
        )
        description = (
            "Open Manual Verification in the dashboard to review pending "
            "members. Approve/reject is not available in Discord."
        )
        if count is not None:
            description = (
                f"**{count}** open manual review"
                f"{'' if count == 1 else 's'}.\n\n{description}"
            )

        embed = discord.Embed(
            title="Verification pending",
            description=description,
            color=discord.Color.blurple(),
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Open dashboard",
                style=discord.ButtonStyle.link,
                url=url,
            )
        )
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )
