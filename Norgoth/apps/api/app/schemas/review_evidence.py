"""Pydantic models for structured manual-review evidence."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BannedAccountEvidence(BaseModel):
    """Resolved banned-account identity snapshot for moderators."""

    model_config = ConfigDict(extra="forbid")

    discord_user_id: str
    display_name: str | None = None
    username: str | None = None
    source: str
    resolved_at: datetime | None = None


class MatchedHighRiskServerEvidence(BaseModel):
    """High Risk Server match snapshot at case creation."""

    model_config = ConfigDict(extra="forbid")

    discord_guild_id: str
    description: str | None = None


class ReviewEvidence(BaseModel):
    """Structured manual-review evidence persisted on verification_attempts."""

    model_config = ConfigDict(extra="forbid")

    reasons: list[str] = Field(default_factory=list)
    matched_banned_accounts: list[BannedAccountEvidence] = Field(default_factory=list)
    matched_high_risk_servers: list[MatchedHighRiskServerEvidence] = Field(
        default_factory=list
    )
    proxy_classification: str | None = None
    evidence_captured_at: datetime


MANUAL_REVIEW_REASON_CODES = frozenset(
    {
        "vpn_or_proxy",
        "shared_ip",
        "banned_ip_match",
        "high_risk_server",
        "membership_check_unavailable",
        "risk_provider_unavailable",
    }
)
