"""Derive selector setup_state from Redis presence + Postgres feature rows."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.db.url import DatabaseConfigurationError
from app.models.feature_configs import (
    HoneypotConfig,
    LevelingConfig,
    ModuleConfig,
    RaidConfig,
    TicketConfig,
)
from app.models.guild import Guild
from app.models.guild_settings import GuildSettings
from app.models.logging_config import LoggingChannel

logger = logging.getLogger(__name__)

SetupState = str


def derive_setup_state(*, bot_installed: bool, configured: bool) -> SetupState:
    """Map install presence + durable config to a selector state."""

    if not bot_installed:
        return "not_installed"
    if configured:
        return "configured"
    return "not_configured"


async def configured_discord_guild_ids(
    session: AsyncSession,
    discord_guild_ids: Iterable[str],
) -> set[str]:
    """Return Discord guild ids that have at least one durable feature row."""

    id_list = [str(guild_id) for guild_id in discord_guild_ids if guild_id]
    if not id_list:
        return set()

    settings_ids = (
        select(Guild.discord_guild_id.label("gid"))
        .join(GuildSettings, GuildSettings.guild_id == Guild.id)
        .where(Guild.discord_guild_id.in_(id_list))
    )
    logging_ids = select(LoggingChannel.guild_id.label("gid")).where(
        LoggingChannel.guild_id.in_(id_list)
    )
    module_ids = select(ModuleConfig.guild_id.label("gid")).where(
        ModuleConfig.guild_id.in_(id_list)
    )
    ticket_ids = select(TicketConfig.guild_id.label("gid")).where(
        TicketConfig.guild_id.in_(id_list)
    )
    raid_ids = select(RaidConfig.guild_id.label("gid")).where(
        RaidConfig.guild_id.in_(id_list)
    )
    honeypot_ids = select(HoneypotConfig.guild_id.label("gid")).where(
        HoneypotConfig.guild_id.in_(id_list)
    )
    leveling_ids = select(LevelingConfig.guild_id.label("gid")).where(
        LevelingConfig.guild_id.in_(id_list)
    )

    stmt = union(
        settings_ids,
        logging_ids,
        module_ids,
        ticket_ids,
        raid_ids,
        honeypot_ids,
        leveling_ids,
    )
    result = await session.execute(stmt)
    return {str(row[0]) for row in result.all() if row[0]}


async def lookup_configured_guild_ids(discord_guild_ids: set[str]) -> set[str]:
    """Load configured ids, or return empty when the database is unavailable."""

    if not discord_guild_ids:
        return set()
    try:
        factory = get_session_factory()
    except DatabaseConfigurationError:
        return set()
    except Exception:
        logger.exception("Could not create a database session for setup_state")
        return set()

    try:
        async with factory() as session:
            return await configured_discord_guild_ids(session, discord_guild_ids)
    except Exception:
        logger.exception("Failed to load guild setup state")
        return set()
