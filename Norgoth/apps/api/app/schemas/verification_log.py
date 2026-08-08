"""Response schemas for Discord verification logs."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import VerificationStatus

DiscordSnowflakeValue = Annotated[
    str,
    Field(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]


class VerificationLogResponse(BaseModel):
    """Public dashboard representation of a verification attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guild_id: UUID
    discord_user_id: DiscordSnowflakeValue
    status: VerificationStatus
    reason: str | None
    vpn_or_proxy_detected: bool
    shared_ip_detected: bool
    blacklisted_guild_detected: bool
    created_at: datetime
