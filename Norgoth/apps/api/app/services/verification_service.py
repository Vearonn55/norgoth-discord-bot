"""Discord verification workflow orchestration."""

from dataclasses import dataclass
from uuid import UUID

from app.models.configuration import Configuration
from app.models.enums import (
    UserListType,
    VerificationStatus,
)
from app.services.blacklisted_guild_service import (
    BlacklistedGuildService,
)
from app.services.user_list_service import UserListService
from app.services.verification_decision_service import (
    VerificationDecisionReason,
    VerificationDecisionService,
    VerificationPolicy,
    VerificationSignals,
)
from app.services.verification_log_service import (
    VerificationLogService,
)


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    """Data collected for one Discord verification attempt."""

    guild_id: UUID
    discord_user_id: str
    discord_user_guild_ids: frozenset[str]
    discord_account_age_days: int
    ip_address: str
    vpn_or_proxy_detected: bool


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Final result returned by the verification workflow."""

    allowed: bool
    reason: VerificationDecisionReason
    shared_ip_detected: bool
    blacklisted_guild_detected: bool


class VerificationService:
    """Run the complete Discord V1 verification workflow."""

    def __init__(
        self,
        *,
        user_list_service: UserListService,
        blacklisted_guild_service: BlacklistedGuildService,
        verification_log_service: VerificationLogService,
        verification_decision_service: VerificationDecisionService,
    ) -> None:
        """Initialize the workflow with required V1 services."""

        self._user_list_service = user_list_service
        self._blacklisted_guild_service = blacklisted_guild_service
        self._verification_log_service = verification_log_service
        self._verification_decision_service = verification_decision_service

    async def verify(
        self,
        *,
        configuration: Configuration,
        request: VerificationRequest,
    ) -> VerificationResult:
        """Evaluate and record one Discord verification attempt."""

        user_list_entry = await self._user_list_service.get_entry(
            guild_id=request.guild_id,
            discord_user_id=request.discord_user_id,
        )

        whitelisted = (
            user_list_entry is not None and user_list_entry.list_type is UserListType.WHITELIST
        )
        user_blacklisted = (
            user_list_entry is not None and user_list_entry.list_type is UserListType.BLACKLIST
        )

        blacklisted_guild_entries = await self._blacklisted_guild_service.list_entries(
            request.guild_id
        )
        blacklisted_guild_ids = {
            entry.blacklisted_discord_guild_id for entry in blacklisted_guild_entries
        }

        blacklisted_guild_detected = bool(request.discord_user_guild_ids & blacklisted_guild_ids)

        shared_ip_detected = await self._verification_log_service.has_shared_ip(
            guild_id=request.guild_id,
            discord_user_id=request.discord_user_id,
            ip_address=request.ip_address,
        )

        decision = self._verification_decision_service.evaluate(
            signals=VerificationSignals(
                whitelisted=whitelisted,
                user_blacklisted=user_blacklisted,
                blacklisted_guild_detected=(blacklisted_guild_detected),
                vpn_or_proxy_detected=request.vpn_or_proxy_detected,
                shared_ip_detected=shared_ip_detected,
                discord_account_age_days=(request.discord_account_age_days),
            ),
            policy=VerificationPolicy(
                minimum_account_age_days=(configuration.minimum_account_age_days),
                deny_vpn_or_proxy=configuration.deny_vpn_or_proxy,
                deny_shared_ip=configuration.deny_shared_ip,
            ),
        )

        await self._verification_log_service.create_log(
            guild_id=request.guild_id,
            discord_user_id=request.discord_user_id,
            status=(VerificationStatus.SUCCESS if decision.allowed else VerificationStatus.FAILED),
            reason=decision.reason.value,
            ip_address=request.ip_address,
            vpn_or_proxy_detected=request.vpn_or_proxy_detected,
            shared_ip_detected=shared_ip_detected,
            blacklisted_guild_detected=blacklisted_guild_detected,
        )

        return VerificationResult(
            allowed=decision.allowed,
            reason=decision.reason,
            shared_ip_detected=shared_ip_detected,
            blacklisted_guild_detected=blacklisted_guild_detected,
        )


__all__ = [
    "VerificationRequest",
    "VerificationResult",
    "VerificationService",
]
