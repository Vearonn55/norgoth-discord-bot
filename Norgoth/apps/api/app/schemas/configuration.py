"""Request and response schemas for verification configuration."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DiscordSnowflakeValue = Annotated[
    str,
    Field(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]


class ConfigurationUpsertRequest(BaseModel):
    """Payload used to create or update guild verification settings."""

    verification_channel_id: DiscordSnowflakeValue
    log_channel_id: DiscordSnowflakeValue
    verified_role_id: DiscordSnowflakeValue
    unverified_role_id: DiscordSnowflakeValue
    member_role_id: DiscordSnowflakeValue
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
    enabled: bool = True


class ConfigurationEnabledRequest(BaseModel):
    """Payload used to enable or disable verification."""

    enabled: bool


class ConfigurationResponse(BaseModel):
    """Public representation of guild verification settings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guild_id: UUID
    verification_channel_id: DiscordSnowflakeValue
    log_channel_id: DiscordSnowflakeValue
    verified_role_id: DiscordSnowflakeValue
    unverified_role_id: DiscordSnowflakeValue
    member_role_id: DiscordSnowflakeValue
    minimum_account_age_days: int
    session_timeout_seconds: int
    deny_vpn_or_proxy: bool
    deny_shared_ip: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime
