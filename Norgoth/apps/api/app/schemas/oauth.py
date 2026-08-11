"""Schemas returned by Discord OAuth endpoints."""

from pydantic import BaseModel, ConfigDict, Field

from app.services.verification_decision_service import (
    VerificationDecisionReason,
)


class DiscordOAuthUserResponse(BaseModel):
    """Public Discord identity returned after authentication."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
        max_length=20,
        pattern=r"^\d+$",
    )
    username: str = Field(min_length=1)
    global_name: str | None
    avatar: str | None


class DiscordVerificationCallbackResponse(BaseModel):
    """Final result returned by the Discord verification callback."""

    model_config = ConfigDict(extra="forbid")

    verification_guild_id: str = Field(
        min_length=1,
        max_length=20,
        pattern=r"^\d+$",
    )
    user: DiscordOAuthUserResponse
    allowed: bool
    reason: VerificationDecisionReason
    shared_ip_detected: bool
    high_risk_guild_detected: bool
