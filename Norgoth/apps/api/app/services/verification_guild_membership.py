"""Bot-backed guild membership checks for member verification."""

from __future__ import annotations

import logging

from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient

logger = logging.getLogger(__name__)


async def resolve_matched_high_risk_guilds(
    bot_client: DiscordBotClient | None,
    *,
    user_id: str,
    high_risk_guild_ids: frozenset[str],
) -> tuple[str, ...]:
    """Return high-risk guild IDs where the user is a member.

    Membership is resolved through the bot REST API, so only guilds where NorBot
    is installed can be checked. A 404 means the user is not a member; other
    failures are logged and skipped to avoid false positives when the bot lacks
    access to a configured high-risk guild.
    """

    if bot_client is None or not high_risk_guild_ids:
        return ()

    matched: list[str] = []
    for guild_id in sorted(high_risk_guild_ids):
        try:
            await bot_client.get_guild_member(guild_id, user_id)
        except DiscordBotAPIError as error:
            if error.status_code == 404:
                continue
            logger.info(
                "high_risk_guild_membership_skipped guild_id=%s status=%s",
                guild_id,
                error.status_code,
            )
            continue
        matched.append(guild_id)

    return tuple(matched)


__all__ = ["resolve_matched_high_risk_guilds"]
