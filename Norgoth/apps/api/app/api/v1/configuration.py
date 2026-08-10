"""Version 1 API endpoints for guild verification configuration."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.v1.dependencies import (
    ConfigurationServiceDependency,
    DatabaseSession,
    GuildServiceDependency,
)
from app.api.v1.dependencies_auth import guild_manager_dependency
from app.schemas.configuration import (
    ConfigurationEnabledRequest,
    ConfigurationResponse,
    ConfigurationUpsertRequest,
    DetectorConfigPatchRequest,
    VerificationStatePatchRequest,
)

router = APIRouter(
    prefix="/guilds/{discord_guild_id}/configuration",
    tags=["configuration"],
    dependencies=[Depends(guild_manager_dependency("discord_guild_id"))],
)

DiscordGuildIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]


@router.get(
    "",
    response_model=ConfigurationResponse,
)
async def get_configuration(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
) -> ConfigurationResponse:
    """Return verification settings for a Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)

    if configuration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guild configuration not found.",
        )

    return ConfigurationResponse.model_validate(configuration)


@router.put(
    "",
    response_model=ConfigurationResponse,
)
async def create_or_update_configuration(
    discord_guild_id: DiscordGuildIdPath,
    payload: ConfigurationUpsertRequest,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    session: DatabaseSession,
) -> ConfigurationResponse:
    """Create or update verification settings for a Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    configuration = await configuration_service.create_or_update(
        guild_id=guild.id,
        verification_channel_id=payload.verification_channel_id,
        log_channel_id=payload.log_channel_id,
        unverified_role_id=payload.unverified_role_id,
        member_role_id=payload.member_role_id,
        manual_review_role_id=payload.manual_review_role_id,
        minimum_account_age_days=payload.minimum_account_age_days,
        session_timeout_seconds=payload.session_timeout_seconds,
        deny_vpn_or_proxy=payload.deny_vpn_or_proxy,
        deny_shared_ip=payload.deny_shared_ip,
        vpn_or_proxy_action=payload.vpn_or_proxy_action,
        shared_ip_action=payload.shared_ip_action,
        enabled=payload.enabled,
    )

    await session.commit()
    await session.refresh(configuration)

    return ConfigurationResponse.model_validate(configuration)


@router.patch(
    "/state",
    response_model=ConfigurationResponse,
)
async def patch_verification_state(
    discord_guild_id: DiscordGuildIdPath,
    payload: VerificationStatePatchRequest,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    session: DatabaseSession,
) -> ConfigurationResponse:
    """Apply one Member Verification master/detector state transition.

    Creates a settings row on demand so the master and detector toggles work
    before channels/roles are configured. Returns the normalized state.
    """

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    configuration = await configuration_service.apply_verification_state(
        guild_id=guild.id,
        enabled=payload.enabled,
        deny_vpn_or_proxy=payload.deny_vpn_or_proxy,
        deny_shared_ip=payload.deny_shared_ip,
    )

    await session.commit()

    return ConfigurationResponse.model_validate(configuration)


@router.patch(
    "/detectors",
    response_model=ConfigurationResponse,
)
async def patch_detectors(
    discord_guild_id: DiscordGuildIdPath,
    payload: DetectorConfigPatchRequest,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    session: DatabaseSession,
) -> ConfigurationResponse:
    """Partially update the VPN/Proxy and Shared IP risk detectors."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    configuration = await configuration_service.patch_detectors(
        guild_id=guild.id,
        deny_vpn_or_proxy=payload.deny_vpn_or_proxy,
        vpn_or_proxy_action=payload.vpn_or_proxy_action,
        deny_shared_ip=payload.deny_shared_ip,
        shared_ip_action=payload.shared_ip_action,
    )

    if configuration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guild configuration not found.",
        )

    await session.commit()

    return ConfigurationResponse.model_validate(configuration)


@router.patch(
    "/enabled",
    response_model=ConfigurationResponse,
)
async def set_configuration_enabled(
    discord_guild_id: DiscordGuildIdPath,
    payload: ConfigurationEnabledRequest,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    session: DatabaseSession,
) -> ConfigurationResponse:
    """Enable or disable verification for a Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    configuration = await configuration_service.set_enabled(
        guild_id=guild.id,
        enabled=payload.enabled,
    )

    if configuration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guild configuration not found.",
        )

    await session.commit()
    await session.refresh(configuration)

    return ConfigurationResponse.model_validate(configuration)
