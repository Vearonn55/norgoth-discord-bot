"""Campaign DM unsubscribe: button + /unsubscribe slash command."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
import httpx
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.campaigns")

UNSUB_PREFIX = "norgoth:campaigns:unsub:"


def unsubscribed_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:campaigns:unsubscribed"


class CampaignsCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def mark_unsubscribed(self, guild_id: int, user_id: int) -> None:
        # Keep Redis hot-path key for immediate worker filtering.
        await self.bot.state.redis.sadd(unsubscribed_key(guild_id), str(user_id))
        api_base = self.bot.settings.api_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{api_base}/internal/campaigns/unsubscribe",
                    headers={"X-Norgoth-Bot-Token": self.bot.settings.token},
                    json={"guild_id": str(guild_id), "user_id": str(user_id)},
                )
            if response.status_code != 200:
                logger.warning(
                    "Campaign unsubscribe durability call failed (%s): %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.HTTPError:
            logger.exception(
                "Campaign unsubscribe durability call failed for guild=%s user=%s",
                guild_id,
                user_id,
            )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type is not discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id") if interaction.data else None
        if not isinstance(custom_id, str) or not custom_id.startswith(UNSUB_PREFIX):
            return

        guild_id_raw = custom_id[len(UNSUB_PREFIX) :]
        if not guild_id_raw.isdigit():
            await interaction.response.send_message(
                "Invalid unsubscribe link.", ephemeral=True
            )
            return

        await self.mark_unsubscribed(int(guild_id_raw), interaction.user.id)
        await interaction.response.send_message(
            "You have been unsubscribed from campaign DMs for that server.",
            ephemeral=True,
        )

    @app_commands.command(
        name="unsubscribe",
        description="Stop receiving campaign DMs from this server",
    )
    async def unsubscribe(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Run /unsubscribe inside the server you want to leave campaign DMs for.",
                ephemeral=True,
            )
            return

        await self.mark_unsubscribed(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            "You will no longer receive campaign DMs from this server.",
            ephemeral=True,
        )
