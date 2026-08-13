"""Flat read-model views assembled from the normalized core tables.

The core identity/verification data is stored normalized (``guilds`` +
``guild_settings`` + ``guild_role_bindings`` + ``guild_channel_bindings`` +
``discord_users``), but the HTTP contract and the OAuth verify flow consume a
flat shape. Services assemble these frozen views so response schemas (which use
``from_attributes=True``) and internal callers keep a stable attribute surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.enums import RiskAction, UserListType, VerificationStatus


@dataclass(frozen=True, slots=True)
class GuildView:
    """Flat representation of a registered guild."""

    id: UUID
    discord_guild_id: str
    discord_guild_name: str
    discord_owner_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ConfigurationView:
    """Flat representation of a guild's verification configuration."""

    id: UUID
    guild_id: UUID
    verification_channel_id: str
    log_channel_id: str
    unverified_role_id: str
    member_role_id: str
    manual_review_role_id: str
    minimum_account_age_days: int
    session_timeout_seconds: int
    deny_vpn_or_proxy: bool
    deny_shared_ip: bool
    vpn_or_proxy_action: RiskAction
    shared_ip_action: RiskAction
    enabled: bool
    panel_message_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ModerationEntryView:
    """Flat representation of a whitelist/blacklist entry."""

    id: UUID
    guild_id: UUID
    discord_user_id: str
    list_type: UserListType
    reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VerificationAttemptView:
    """Flat representation of a verification attempt for the API/dashboard."""

    id: UUID
    guild_id: UUID
    discord_user_id: str
    status: VerificationStatus
    reason: str | None
    vpn_or_proxy_detected: bool
    shared_ip_detected: bool
    high_risk_guild_detected: bool
    matched_high_risk_guild_ids: tuple[str, ...]
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
