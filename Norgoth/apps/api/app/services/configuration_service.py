"""Business operations for Discord verification configuration."""

from uuid import UUID

from app.models.configuration import Configuration
from app.repositories.configuration_repository import (
    ConfigurationRepository,
)


class ConfigurationService:
    """Manage verification settings for Discord guilds."""

    def __init__(
        self,
        configuration_repository: ConfigurationRepository,
    ) -> None:
        """Initialize the service with its configuration repository."""

        self._configuration_repository = configuration_repository

    async def get_by_guild_id(
        self,
        guild_id: UUID,
    ) -> Configuration | None:
        """Return the configuration belonging to a Discord guild."""

        return await self._configuration_repository.get_by_guild_id(guild_id)

    async def create_or_update(
        self,
        *,
        guild_id: UUID,
        verification_channel_id: str,
        log_channel_id: str,
        verified_role_id: str,
        unverified_role_id: str,
        member_role_id: str,
        minimum_account_age_days: int,
        session_timeout_seconds: int,
        deny_vpn_or_proxy: bool,
        deny_shared_ip: bool,
        enabled: bool,
    ) -> Configuration:
        """Create or update the verification configuration for a guild."""

        configuration = await self._configuration_repository.get_by_guild_id(guild_id)

        if configuration is None:
            configuration = Configuration(
                guild_id=guild_id,
                verification_channel_id=verification_channel_id,
                log_channel_id=log_channel_id,
                verified_role_id=verified_role_id,
                unverified_role_id=unverified_role_id,
                member_role_id=member_role_id,
                minimum_account_age_days=minimum_account_age_days,
                session_timeout_seconds=session_timeout_seconds,
                deny_vpn_or_proxy=deny_vpn_or_proxy,
                deny_shared_ip=deny_shared_ip,
                enabled=enabled,
            )

            return await self._configuration_repository.add(configuration)

        configuration.verification_channel_id = verification_channel_id
        configuration.log_channel_id = log_channel_id
        configuration.verified_role_id = verified_role_id
        configuration.unverified_role_id = unverified_role_id
        configuration.member_role_id = member_role_id
        configuration.minimum_account_age_days = minimum_account_age_days
        configuration.session_timeout_seconds = session_timeout_seconds
        configuration.deny_vpn_or_proxy = deny_vpn_or_proxy
        configuration.deny_shared_ip = deny_shared_ip
        configuration.enabled = enabled

        return await self._configuration_repository.save(configuration)

    async def set_enabled(
        self,
        *,
        guild_id: UUID,
        enabled: bool,
    ) -> Configuration | None:
        """Enable or disable verification for an existing configuration."""

        configuration = await self._configuration_repository.get_by_guild_id(guild_id)

        if configuration is None:
            return None

        configuration.enabled = enabled

        return await self._configuration_repository.save(configuration)
