"""Discord verification workflow orchestration."""

from dataclasses import dataclass
from uuid import UUID

from app.models.enums import (
    UserListType,
    VerificationStatus,
)
from app.services.high_risk_guild_service import HighRiskGuildService
from app.services.user_list_service import UserListService
from app.services.verification_decision_service import (
    VerificationDecisionReason,
    VerificationDecisionService,
    VerificationOutcome,
    VerificationPolicy,
    VerificationSignals,
)
from app.services.verification_log_service import (
    VerificationLogService,
)
from app.services.views import ConfigurationView

_OUTCOME_TO_STATUS = {
    VerificationOutcome.ALLOW: VerificationStatus.SUCCESS,
    VerificationOutcome.DENY: VerificationStatus.FAILED,
    VerificationOutcome.MANUAL_REVIEW: VerificationStatus.MANUAL_REVIEW,
}


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
    manual_review: bool
    reason: VerificationDecisionReason
    shared_ip_detected: bool
    high_risk_guild_detected: bool
    matched_high_risk_guild_ids: tuple[str, ...]


class VerificationService:
    """Run the complete Discord V1 verification workflow."""

    def __init__(
        self,
        *,
        user_list_service: UserListService,
        high_risk_guild_service: HighRiskGuildService,
        verification_log_service: VerificationLogService,
        verification_decision_service: VerificationDecisionService,
    ) -> None:
        """Initialize the workflow with required V1 services."""

        self._user_list_service = user_list_service
        self._high_risk_guild_service = high_risk_guild_service
        self._verification_log_service = verification_log_service
        self._verification_decision_service = verification_decision_service

    async def verify(
        self,
        *,
        configuration: ConfigurationView,
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

        high_risk_guild_entries = await self._high_risk_guild_service.list_entries(
            request.guild_id
        )
        high_risk_guild_ids = {
            entry.high_risk_discord_guild_id for entry in high_risk_guild_entries
        }
        # Capture exactly which configured high-risk servers the user belongs to
        # so reviewers see an explicit, auditable reason (sorted for stability).
        matched_high_risk_guild_ids = tuple(
            sorted(request.discord_user_guild_ids & high_risk_guild_ids)
        )
        high_risk_guild_detected = bool(matched_high_risk_guild_ids)

        # Only run shared-IP (alt-account) correlation when the detector is
        # enabled; a disabled detector must not influence the decision or leave
        # a signal on the attempt.
        shared_ip_detected = False
        if configuration.deny_shared_ip:
            shared_ip_detected = await self._verification_log_service.has_shared_ip(
                guild_id=request.guild_id,
                discord_user_id=request.discord_user_id,
                ip_address=request.ip_address,
            )

        decision = self._verification_decision_service.evaluate(
            signals=VerificationSignals(
                whitelisted=whitelisted,
                user_blacklisted=user_blacklisted,
                vpn_or_proxy_detected=request.vpn_or_proxy_detected,
                shared_ip_detected=shared_ip_detected,
                discord_account_age_days=(request.discord_account_age_days),
                high_risk_guild_detected=high_risk_guild_detected,
            ),
            policy=VerificationPolicy(
                minimum_account_age_days=(configuration.minimum_account_age_days),
                deny_vpn_or_proxy=configuration.deny_vpn_or_proxy,
                deny_shared_ip=configuration.deny_shared_ip,
                vpn_or_proxy_action=configuration.vpn_or_proxy_action,
                shared_ip_action=configuration.shared_ip_action,
            ),
        )

        await self._verification_log_service.create_log(
            guild_id=request.guild_id,
            discord_user_id=request.discord_user_id,
            status=_OUTCOME_TO_STATUS[decision.outcome],
            reason=decision.reason.value,
            ip_address=request.ip_address,
            vpn_or_proxy_detected=request.vpn_or_proxy_detected,
            shared_ip_detected=shared_ip_detected,
            high_risk_guild_detected=high_risk_guild_detected,
            matched_high_risk_guild_ids=list(matched_high_risk_guild_ids),
        )

        return VerificationResult(
            allowed=decision.allowed,
            manual_review=decision.manual_review,
            reason=decision.reason,
            shared_ip_detected=shared_ip_detected,
            high_risk_guild_detected=high_risk_guild_detected,
            matched_high_risk_guild_ids=matched_high_risk_guild_ids,
        )


__all__ = [
    "VerificationRequest",
    "VerificationResult",
    "VerificationService",
]
