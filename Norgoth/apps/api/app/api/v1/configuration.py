"""Version 1 API endpoints for guild verification configuration."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from app.api.v1.dependencies import (
    ConfigurationServiceDependency,
    DatabaseSession,
    DiscordBotClientDependency,
    GuildServiceDependency,
)
from app.api.v1.dependencies_auth import guild_manager_dependency
from app.schemas.configuration import (
    ConfigurationEnabledRequest,
    ConfigurationResponse,
    ConfigurationUpsertRequest,
    DetectorConfigPatchRequest,
    VerificationSetupResponse,
    VerificationStatePatchRequest,
    VerificationValidateResponse,
)
from app.services.verification_discord_validate import (
    validate_verification_discord_resources,
)
from app.services.verification_join_config import invalidate_verification_join_cache
from app.services.verification_setup import derive_verification_setup_state
from app.services.views import ConfigurationView

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


def _to_response(configuration: ConfigurationView) -> ConfigurationResponse:
    setup = derive_verification_setup_state(configuration)
    payload = ConfigurationResponse.model_validate(configuration)
    return payload.model_copy(
        update={
            "setup_state": setup.state,
            "missing_bindings": list(setup.missing),
        }
    )


async def _invalidate_join(discord_guild_id: str) -> None:
    await invalidate_verification_join_cache(discord_guild_id)


def _provisional_configuration_view(
    guild_id: UUID,
    payload: ConfigurationUpsertRequest,
) -> ConfigurationView:
    """Build an in-memory configuration view from a draft upsert payload."""

    return ConfigurationView(
        id=uuid4(),
        guild_id=guild_id,
        verification_channel_id=payload.verification_channel_id,
        log_channel_id=payload.log_channel_id,
        unverified_role_id=payload.unverified_role_id,
        member_role_id=payload.member_role_id,
        manual_review_role_id=payload.manual_review_role_id or "",
        minimum_account_age_days=payload.minimum_account_age_days,
        session_timeout_seconds=payload.session_timeout_seconds,
        deny_vpn_or_proxy=payload.deny_vpn_or_proxy,
        deny_shared_ip=payload.deny_shared_ip,
        vpn_or_proxy_action=payload.vpn_or_proxy_action,
        shared_ip_action=payload.shared_ip_action,
        enabled=payload.enabled,
        panel_message_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _validation_issues_response(
    *,
    setup_state: str,
    issues: list[dict[str, str | None]],
) -> VerificationValidateResponse:
    return VerificationValidateResponse(
        ok=False,
        setup_state=setup_state,
        issues=issues,
    )


@router.get(
    "/setup",
    response_model=VerificationSetupResponse,
)
async def get_verification_setup(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
) -> VerificationSetupResponse:
    """Return verification readiness even when settings are missing."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)
    setup = derive_verification_setup_state(configuration)
    return VerificationSetupResponse(
        setup_state=setup.state,
        missing_bindings=list(setup.missing),
        enabled=bool(configuration.enabled) if configuration is not None else False,
        guild_name=guild.discord_guild_name,
    )


@router.post(
    "/validate",
    response_model=VerificationValidateResponse,
)
async def validate_verification_configuration(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    bot_client: DiscordBotClientDependency,
    payload: ConfigurationUpsertRequest | None = Body(default=None),
) -> VerificationValidateResponse:
    """Validate configured Discord channels/roles for verification."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    if bot_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "guild_metadata_unavailable",
                "message": "Discord bot token is not configured.",
            },
        )

    if payload is not None:
        configuration = _provisional_configuration_view(guild.id, payload)
        setup = derive_verification_setup_state(configuration)
        if setup.state in {"not_configured", "incomplete"}:
            return _validation_issues_response(
                setup_state=setup.state,
                issues=[
                    {
                        "code": setup.code,
                        "message": "Required channels and roles are missing from this draft.",
                        "field": None,
                    }
                ],
            )
    else:
        configuration = await configuration_service.get_by_guild_id(guild.id)
        setup = derive_verification_setup_state(configuration)
        if configuration is None or setup.state in {"not_configured", "incomplete"}:
            return _validation_issues_response(
                setup_state=setup.state,
                issues=[
                    {
                        "code": setup.code,
                        "message": "Save required channels and roles before validating.",
                        "field": None,
                    }
                ],
            )

    result = await validate_verification_discord_resources(
        bot_client=bot_client,
        discord_guild_id=discord_guild_id,
        configuration=configuration,
    )
    persisted_setup = derive_verification_setup_state(configuration)
    return VerificationValidateResponse(
        ok=result.ok,
        setup_state=result.setup_state if not result.ok else persisted_setup.state,
        issues=[
            {"code": issue.code, "message": issue.message, "field": issue.field}
            for issue in result.issues
        ],
    )


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

    return _to_response(configuration)


@router.put(
    "",
    response_model=ConfigurationResponse,
)
async def create_or_update_configuration(
    discord_guild_id: DiscordGuildIdPath,
    payload: ConfigurationUpsertRequest,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    bot_client: DiscordBotClientDependency,
    session: DatabaseSession,
) -> ConfigurationResponse:
    """Create or update verification settings for a Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    if bot_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "guild_metadata_unavailable",
                "message": "Discord bot token is not configured.",
            },
        )

    provisional = _provisional_configuration_view(guild.id, payload)
    validation = await validate_verification_discord_resources(
        bot_client=bot_client,
        discord_guild_id=discord_guild_id,
        configuration=provisional,
    )
    if not validation.ok:
        primary = validation.issues[0]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": primary.code,
                "message": primary.message,
                "field": primary.field,
                "issues": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "field": issue.field,
                    }
                    for issue in validation.issues
                ],
            },
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
    await _invalidate_join(discord_guild_id)

    return _to_response(configuration)


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
    await _invalidate_join(discord_guild_id)

    return _to_response(configuration)


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
    await _invalidate_join(discord_guild_id)

    return _to_response(configuration)


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
    await _invalidate_join(discord_guild_id)

    return _to_response(configuration)
