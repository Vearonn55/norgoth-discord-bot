"""Response schemas for Discord verification logs and manual review."""

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


class VerificationReviewRequest(BaseModel):
    """Admin decision on a manual-review verification attempt."""

    approved: bool


class VerificationLogResponse(BaseModel):
    """Public dashboard representation of a verification attempt.

    Includes optional, best-effort Discord identity (display name, username,
    avatar) resolved from the guild member snapshot. Identity is never
    authoritative — the Discord user ID is the source of truth.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guild_id: UUID
    discord_user_id: DiscordSnowflakeValue
    display_name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    status: VerificationStatus
    reason: str | None
    vpn_or_proxy_detected: bool
    shared_ip_detected: bool
    high_risk_guild_detected: bool
    matched_high_risk_guild_ids: list[str] = Field(default_factory=list)
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime


class VerificationLogListResponse(BaseModel):
    """Paginated envelope for verification attempts (server-side paging)."""

    items: list[VerificationLogResponse]
    total: int


class MatchedHighRiskServer(BaseModel):
    """A configured High Risk Server the reviewed user belongs to."""

    discord_guild_id: DiscordSnowflakeValue
    reason: str | None = None


class VerificationLogDetailResponse(VerificationLogResponse):
    """Read-only transcript detail for a single verification attempt.

    Adds the resolved High Risk Server matches (id + configured reason) so a
    reviewer sees the explicit trigger without exposing any IP data.
    """

    matched_high_risk_servers: list[MatchedHighRiskServer] = Field(
        default_factory=list
    )
