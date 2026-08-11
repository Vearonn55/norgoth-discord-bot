"""Automatic responses: keyword-triggered replies with per-rule cooldowns."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.autoresponder")


def autoresponses_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:autoresponses"


def rule_cooldown_key(guild_id: int | str, rule_id: str) -> str:
    return f"norgoth:guild:{guild_id}:autoresponses:cooldown:{rule_id}"


def rule_matches(rule: dict[str, Any], content: str) -> bool:
    trigger = str(rule.get("trigger", "")).strip().lower()

    if not trigger:
        return False

    text = content.lower()
    match_type = rule.get("match_type", "contains")

    if match_type == "exact":
        return text.strip() == trigger
    if match_type == "starts_with":
        return text.lstrip().startswith(trigger)
    return trigger in text


class AutoResponderCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def get_rules(self, guild_id: int) -> list[dict[str, Any]]:
        stored = await self.bot.state.get_json(autoresponses_key(guild_id))
        rules = stored.get("rules", [])
        return rules if isinstance(rules, list) else []

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot or not message.content:
            return

        guild = message.guild

        if not await self.bot.state.is_module_enabled(guild.id, "autoresponder"):
            return

        rules = await self.get_rules(guild.id)

        if not rules:
            return

        for rule in rules:
            if not isinstance(rule, dict) or not rule.get("enabled", True):
                continue

            channel_id = rule.get("channel_id")

            if channel_id and str(message.channel.id) != str(channel_id):
                continue

            if not rule_matches(rule, message.content):
                continue

            rule_id = str(rule.get("id", ""))
            cooldown = int(rule.get("cooldown_seconds", 10) or 0)

            if rule_id and cooldown > 0:
                allowed = await self.bot.state.redis.set(
                    rule_cooldown_key(guild.id, rule_id),
                    "1",
                    ex=cooldown,
                    nx=True,
                )

                if not allowed:
                    continue

            response = str(rule.get("response", "")).strip()

            if not response:
                continue

            rendered = (
                response.replace("{user}", message.author.mention)
                .replace(
                    "{username}",
                    getattr(message.author, "display_name", message.author.name),
                )
                .replace("{server}", guild.name)
            )

            try:
                await message.channel.send(rendered[:2000])
            except discord.HTTPException:
                logger.exception(
                    "Failed to send auto-response in guild %s", guild.id
                )

            # One response per message keeps rule interactions predictable.
            return
