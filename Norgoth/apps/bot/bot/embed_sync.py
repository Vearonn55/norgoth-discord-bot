"""Detect external deletion of published embed-message copies.

The API tracks each published embed copy (``EmbedMessageDelivery``) with its
Discord message id. When a server admin deletes one of those messages directly
in Discord, the dashboard's sync state (e.g. 3/3) becomes stale. These raw
delete listeners notify the API so the affected delivery flips to
``message_missing`` (3/3 → 2/3) immediately, without on-demand polling.
"""

from __future__ import annotations

import logging

import discord
import httpx
from discord.ext import commands

logger = logging.getLogger("norgoth.embed_sync")


class EmbedSyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _notify_deleted(self, message_ids: list[str]) -> None:
        ids = [str(mid) for mid in message_ids if mid]
        if not ids:
            return

        base = self.bot.settings.api_base_url  # type: ignore[attr-defined]
        token = self.bot.settings.token  # type: ignore[attr-defined]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{base}/internal/embed-deliveries/mark-deleted",
                    json={"message_ids": ids},
                    headers={"X-Norgoth-Bot-Token": token},
                )
            if response.status_code != 200:
                logger.debug(
                    "mark-deleted returned HTTP %s: %s",
                    response.status_code,
                    response.text,
                )
        except httpx.HTTPError:
            # Drift detection is best-effort; the dashboard's manual reconcile
            # (or next publish/re-sync) will still correct the state.
            logger.debug("Failed to notify API of deleted embed copy", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self,
        payload: discord.RawMessageDeleteEvent,
    ) -> None:
        if payload.message_id is not None:
            await self._notify_deleted([str(payload.message_id)])

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
    ) -> None:
        await self._notify_deleted([str(mid) for mid in payload.message_ids])
