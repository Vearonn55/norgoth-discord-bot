"""Dependency providers for version 1 API services."""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_database_session
from app.integrations.discord.bot_rest import DiscordBotClient
from app.integrations.discord.oauth import DiscordOAuthClient
from app.integrations.proxycheck import ProxycheckClient
from app.repositories.configuration_repository import (
    ConfigurationRepository,
)
from app.repositories.discord_guild_repository import (
    DiscordGuildRepository,
)
from app.repositories.guild_active_ban_repository import GuildActiveBanRepository
from app.repositories.high_risk_guild_repository import (
    HighRiskGuildRepository,
)
from app.repositories.user_list_repository import (
    UserListRepository,
)
from app.repositories.verification_log_repository import (
    VerificationLogRepository,
)
from app.security.ip_protection import IPProtectionService
from app.security.oauth_state import DiscordOAuthStateService
from app.services.configuration_service import (
    ConfigurationService,
)
from app.services.guild_ban_service import GuildBanService
from app.services.guild_service import GuildService
from app.services.high_risk_guild_service import HighRiskGuildService
from app.services.user_list_service import UserListService
from app.services.verification_decision_service import (
    VerificationDecisionService,
)
from app.services.verification_log_service import (
    VerificationLogService,
)
from app.services.verification_service import VerificationService

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]

SettingsDependency = Annotated[
    Settings,
    Depends(get_settings),
]


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Provide an HTTP client for one API request."""

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=False,
    ) as client:
        yield client


HTTPClientDependency = Annotated[
    httpx.AsyncClient,
    Depends(get_http_client),
]


def _require_discord_oauth_settings(
    settings: Settings,
) -> tuple[str, str, str]:
    """Return complete Discord OAuth settings or fail clearly."""

    if (
        settings.discord_client_id is None
        or settings.discord_client_secret is None
        or settings.discord_redirect_uri is None
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Discord OAuth is not configured. Uncomment and set "
                "NORGOTH_DISCORD_CLIENT_ID, NORGOTH_DISCORD_CLIENT_SECRET, "
                "and NORGOTH_DISCORD_REDIRECT_URI in Norgoth/.env "
                "(redirect must match the Discord Developer Portal)."
            ),
        )

    return (
        settings.discord_client_id,
        settings.discord_client_secret,
        settings.discord_redirect_uri,
    )


def get_discord_oauth_client(
    settings: SettingsDependency,
    http_client: HTTPClientDependency,
) -> DiscordOAuthClient:
    """Create the Discord OAuth client from application settings."""

    client_id, client_secret, redirect_uri = _require_discord_oauth_settings(settings)

    return DiscordOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        http_client=http_client,
    )


DiscordOAuthClientDependency = Annotated[
    DiscordOAuthClient,
    Depends(get_discord_oauth_client),
]


def get_discord_bot_client(
    settings: SettingsDependency,
    http_client: HTTPClientDependency,
) -> DiscordBotClient | None:
    """Create the bot-token REST client, or None when no token is set."""

    if settings.discord_bot_token is None:
        return None

    return DiscordBotClient(
        bot_token=settings.discord_bot_token,
        http_client=http_client,
    )


DiscordBotClientDependency = Annotated[
    DiscordBotClient | None,
    Depends(get_discord_bot_client),
]


def get_discord_oauth_state_service(
    settings: SettingsDependency,
) -> DiscordOAuthStateService:
    """Create the signed Discord OAuth state service."""

    _, client_secret, _ = _require_discord_oauth_settings(settings)

    return DiscordOAuthStateService(
        secret=client_secret,
        lifetime_seconds=600,
    )


DiscordOAuthStateServiceDependency = Annotated[
    DiscordOAuthStateService,
    Depends(get_discord_oauth_state_service),
]


def get_proxycheck_client(
    settings: SettingsDependency,
    http_client: HTTPClientDependency,
) -> ProxycheckClient:
    """Create the proxycheck.io IP reputation client."""

    return ProxycheckClient(
        http_client=http_client,
        api_key=settings.proxycheck_api_key,
    )


ProxycheckClientDependency = Annotated[
    ProxycheckClient,
    Depends(get_proxycheck_client),
]


def get_ip_protection_service(
    settings: SettingsDependency,
) -> IPProtectionService:
    """Create the IP protection service from configured secrets."""

    if settings.ip_hash_key is None or settings.ip_encryption_key is None:
        message = (
            "IP protection keys are not configured. Set "
            "NORGOTH_IP_HASH_KEY and NORGOTH_IP_ENCRYPTION_KEY."
        )
        raise RuntimeError(message)

    return IPProtectionService(
        hash_key=settings.ip_hash_key,
        encryption_key=settings.ip_encryption_key,
    )


IPProtectionServiceDependency = Annotated[
    IPProtectionService,
    Depends(get_ip_protection_service),
]


def get_guild_service(
    session: DatabaseSession,
) -> GuildService:
    """Create a guild service for the current request."""

    return GuildService(
        DiscordGuildRepository(session),
    )


def get_configuration_service(
    session: DatabaseSession,
) -> ConfigurationService:
    """Create a configuration service for the current request."""

    return ConfigurationService(
        ConfigurationRepository(session),
    )


def get_user_list_service(
    session: DatabaseSession,
) -> UserListService:
    """Create a user-list service for the current request."""

    return UserListService(
        UserListRepository(session),
    )


def get_high_risk_guild_service(
    session: DatabaseSession,
) -> HighRiskGuildService:
    """Create a high-risk-guild service for the current request."""

    return HighRiskGuildService(
        HighRiskGuildRepository(session),
    )


def get_verification_log_service(
    session: DatabaseSession,
    ip_protection_service: IPProtectionServiceDependency,
) -> VerificationLogService:
    """Create a verification-log service for the current request."""

    return VerificationLogService(
        VerificationLogRepository(session),
        ip_protection_service,
    )


GuildServiceDependency = Annotated[
    GuildService,
    Depends(get_guild_service),
]

ConfigurationServiceDependency = Annotated[
    ConfigurationService,
    Depends(get_configuration_service),
]

UserListServiceDependency = Annotated[
    UserListService,
    Depends(get_user_list_service),
]

HighRiskGuildServiceDependency = Annotated[
    HighRiskGuildService,
    Depends(get_high_risk_guild_service),
]

VerificationLogServiceDependency = Annotated[
    VerificationLogService,
    Depends(get_verification_log_service),
]


def get_guild_ban_service(
    session: DatabaseSession,
    ip_protection_service: IPProtectionServiceDependency,
) -> GuildBanService:
    """Create a guild-ban service for the current request."""

    return GuildBanService(
        guild_repository=DiscordGuildRepository(session),
        ban_repository=GuildActiveBanRepository(session),
        ip_protection_service=ip_protection_service,
    )


GuildBanServiceDependency = Annotated[
    GuildBanService,
    Depends(get_guild_ban_service),
]


def get_verification_service(
    user_list_service: UserListServiceDependency,
    high_risk_guild_service: HighRiskGuildServiceDependency,
    verification_log_service: VerificationLogServiceDependency,
    guild_ban_service: GuildBanServiceDependency,
    bot_client: DiscordBotClientDependency,
) -> VerificationService:
    """Create the complete Discord verification workflow."""

    return VerificationService(
        user_list_service=user_list_service,
        high_risk_guild_service=high_risk_guild_service,
        verification_log_service=verification_log_service,
        verification_decision_service=VerificationDecisionService(),
        guild_ban_service=guild_ban_service,
        bot_client=bot_client,
    )


VerificationServiceDependency = Annotated[
    VerificationService,
    Depends(get_verification_service),
]
