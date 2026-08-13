"""Rich Link Embeds: reply with embed-friendly social URL rewrites."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from bot.rich_link_embeds_transform import transform_message_urls

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.rich_link_embeds")

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "platforms": {
        "twitter": True,
        "bluesky": True,
        "tiktok": True,
        "reddit": True,
    },
    "channel_allowlist": [],
    "channel_denylist": [],
    "ignore_bots": True,
    "process_edits": False,
    "max_links_per_message": 3,
    "rewrite_hosts": {
        "twitter": "fxtwitter.com",
        "bluesky": "bskx.app",
        "tiktok": "vxtiktok.com",
        "reddit": "vxreddit.com",
    },
    "disclosure_acknowledged": False,
}

SEEN_TTL_SECONDS = 3600


def config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:rich_link_embeds"


def seen_key(guild_id: int | str, message_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:rich_link_embeds:seen:{message_id}"


class RichLinkEmbedsCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(config_key(guild_id))
        if not stored:
            hydrated = await self.bot.state._hydrate_feature_from_api(
                guild_id, "rich_link_embeds"
            )
            if hydrated:
                await self.bot.state.set_json(config_key(guild_id), hydrated)
                stored = hydrated
        if not isinstance(stored, dict):
            return dict(DEFAULT_CONFIG)
        merged = {**DEFAULT_CONFIG, **stored}
        platforms = {
            **DEFAULT_CONFIG["platforms"],
            **(stored.get("platforms") or {}),
        }
        hosts = {
            **DEFAULT_CONFIG["rewrite_hosts"],
            **(stored.get("rewrite_hosts") or {}),
        }
        merged["platforms"] = platforms
        merged["rewrite_hosts"] = hosts
        return merged

    def channel_allowed(self, channel_id: str, config: dict[str, Any]) -> bool:
        denylist = {str(x) for x in (config.get("channel_denylist") or [])}
        if channel_id in denylist:
            return False
        allowlist = [str(x) for x in (config.get("channel_allowlist") or [])]
        if not allowlist:
            return True
        return channel_id in set(allowlist)

    async def _mark_seen(self, guild_id: int, message_id: int) -> bool:
        """Return True if this message was not yet processed (claim acquired)."""

        redis = self.bot.state.redis
        key = seen_key(guild_id, message_id)
        try:
            claimed = await redis.set(key, "1", nx=True, ex=SEEN_TTL_SECONDS)
            return bool(claimed)
        except Exception:  # noqa: BLE001 — degrade to process once without Redis
            logger.debug("rich_link_embeds seen-set unavailable", exc_info=True)
            return True

    async def _handle(self, message: discord.Message, *, is_edit: bool) -> None:
        if message.guild is None or self.bot.user is None:
            return
        if message.author.id == self.bot.user.id:
            return
        if message.webhook_id is not None:
            return

        if not await self.bot.state.is_module_enabled(
            message.guild.id, "rich_link_embeds"
        ):
            return

        config = await self.get_config(message.guild.id)
        if not config.get("enabled"):
            return
        if is_edit and not config.get("process_edits"):
            return
        if config.get("ignore_bots", True) and message.author.bot:
            return
        if not self.channel_allowed(str(message.channel.id), config):
            return
        if not message.content or not message.content.strip():
            return

        max_links = int(config.get("max_links_per_message") or 3)
        rewritten = transform_message_urls(
            message.content,
            enabled_platforms=dict(config.get("platforms") or {}),
            rewrite_hosts=dict(config.get("rewrite_hosts") or {}),
            max_links=max_links,
        )
        if not rewritten:
            return

        if not await self._mark_seen(message.guild.id, message.id):
            return

        try:
            await message.reply(
                "\n".join(rewritten),
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            logger.info(
                "rich_link_embeds reply failed guild=%s channel=%s",
                message.guild.id,
                message.channel.id,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._handle(message, is_edit=False)

    @commands.Cog.listener()
    async def on_message_edit(
        self, _before: discord.Message, after: discord.Message
    ) -> None:
        await self._handle(after, is_edit=True)
