"""OAuth-backed guild membership checks for member verification."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.integrations.discord.oauth import DiscordOAuthClient, DiscordOAuthError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HighRiskMembershipResult:
    """Outcome of matching configured high-risk servers against user guilds."""

    matched_high_risk_guild_ids: tuple[str, ...]
    membership_check_unavailable: bool


def resolve_matched_high_risk_guilds_from_user_guilds(
    *,
    user_guild_ids: frozenset[str],
    high_risk_guild_ids: frozenset[str],
) -> tuple[str, ...]:
    """Return configured high-risk guild IDs present in the user's guild list."""

    if not high_risk_guild_ids:
        return ()
    return tuple(sorted(user_guild_ids & high_risk_guild_ids))


async def resolve_high_risk_membership(
    oauth_client: DiscordOAuthClient,
    *,
    access_token: str,
    token_scopes: frozenset[str],
    high_risk_guild_ids: frozenset[str],
) -> HighRiskMembershipResult:
    """Match configured high-risk servers using the verifying user's OAuth guilds."""

    if not high_risk_guild_ids:
        return HighRiskMembershipResult((), False)

    if "guilds" not in token_scopes:
        logger.info("high_risk_membership_unavailable missing_guilds_scope")
        return HighRiskMembershipResult((), True)

    try:
        user_guild_ids = await oauth_client.get_current_user_guild_ids(
            access_token=access_token,
        )
    except DiscordOAuthError as error:
        logger.info(
            "high_risk_membership_unavailable operation=%s status=%s",
            error.operation,
            error.http_status,
        )
        return HighRiskMembershipResult((), True)

    matched = resolve_matched_high_risk_guilds_from_user_guilds(
        user_guild_ids=user_guild_ids,
        high_risk_guild_ids=high_risk_guild_ids,
    )
    return HighRiskMembershipResult(matched, False)


__all__ = [
    "HighRiskMembershipResult",
    "resolve_high_risk_membership",
    "resolve_matched_high_risk_guilds_from_user_guilds",
]
