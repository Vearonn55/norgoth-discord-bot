"""Request and response schemas for verification configuration."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RiskAction

DiscordSnowflakeValue = Annotated[
    str,
    Field(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]

OptionalDiscordSnowflakeValue = Annotated[
    str,
    Field(
        max_length=20,
        pattern=r"^([0-9]{1,20})?$",
    ),
]


class ConfigurationUpsertRequest(BaseModel):
    """Payload used to create or update guild verification settings."""

    verification_channel_id: DiscordSnowflakeValue
    log_channel_id: DiscordSnowflakeValue
    unverified_role_id: DiscordSnowflakeValue
    member_role_id: DiscordSnowflakeValue
    manual_review_role_id: OptionalDiscordSnowflakeValue = ""
    minimum_account_age_days: Annotated[
        int,
        Field(
            ge=0,
            le=3650,
        ),
    ] = 0
    session_timeout_seconds: Annotated[
        int,
        Field(
            ge=60,
            le=3600,
        ),
    ] = 900
    deny_vpn_or_proxy: bool = True
    deny_shared_ip: bool = True
    vpn_or_proxy_action: RiskAction = RiskAction.DENY
    shared_ip_action: RiskAction = RiskAction.DENY
    enabled: bool = True


class ConfigurationEnabledRequest(BaseModel):
    """Payload used to enable or disable verification."""

    enabled: bool


class DetectorConfigPatchRequest(BaseModel):
    """Partial update for the VPN/Proxy and Shared IP risk detectors.

    Every field is optional so the detector mini-cards can persist a single
    toggle or action change without resubmitting the full configuration.
    """

    deny_vpn_or_proxy: bool | None = None
    vpn_or_proxy_action: RiskAction | None = None
    deny_shared_ip: bool | None = None
    shared_ip_action: RiskAction | None = None


class VerificationStatePatchRequest(BaseModel):
    """Single-intent transition for the Member Verification state machine.

    Send exactly one intent: the master (`enabled`) or one detector flag. The
    backend derives the full coherent (master, vpn, shared) state and rejects
    the invalid master-ON/both-OFF combination.
    """

    enabled: bool | None = None
    deny_vpn_or_proxy: bool | None = None
    deny_shared_ip: bool | None = None


class ConfigurationResponse(BaseModel):
    """Public representation of guild verification settings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guild_id: UUID
    verification_channel_id: DiscordSnowflakeValue
    log_channel_id: DiscordSnowflakeValue
    unverified_role_id: DiscordSnowflakeValue
    member_role_id: DiscordSnowflakeValue
    manual_review_role_id: OptionalDiscordSnowflakeValue = ""
    minimum_account_age_days: int
    session_timeout_seconds: int
    deny_vpn_or_proxy: bool
    deny_shared_ip: bool
    vpn_or_proxy_action: RiskAction
    shared_ip_action: RiskAction
    enabled: bool
    created_at: datetime
    updated_at: datetime
