"""Discord verification workflow orchestration."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.integrations.discord.bot_rest import DiscordBotClient
from app.models.enums import (
    UserListType,
    VerificationStatus,
)
from app.schemas.review_evidence import (
    MatchedHighRiskServerEvidence,
    ReviewEvidence,
)
from app.services.guild_ban_service import GuildBanService
from app.services.high_risk_guild_service import HighRiskGuildService
from app.services.user_list_service import UserListService
from app.services.verification_banned_identity import (
    resolve_banned_account_identities,
)
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
from app.services.verification_review_reasons import derive_manual_review_reason_codes
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
    discord_guild_id: str
    matched_high_risk_guild_ids: tuple[str, ...]
    discord_account_age_days: int
    ip_address: str
    vpn_or_proxy_detected: bool
    membership_check_unavailable: bool = False
    risk_provider_unavailable: bool = False
    proxy_classification: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Final result returned by the verification workflow."""

    allowed: bool
    manual_review: bool
    reason: VerificationDecisionReason
    shared_ip_detected: bool
    high_risk_guild_detected: bool
    matched_high_risk_guild_ids: tuple[str, ...]
    banned_ip_match_detected: bool
    matched_banned_user_ids: tuple[str, ...]
    review_evidence: ReviewEvidence | None
    attempt_id: UUID | None = None
    created_at: datetime | None = None


class VerificationService:
    """Run the complete Discord V1 verification workflow."""

    def __init__(
        self,
        *,
        user_list_service: UserListService,
        high_risk_guild_service: HighRiskGuildService,
        verification_log_service: VerificationLogService,
        verification_decision_service: VerificationDecisionService,
        guild_ban_service: GuildBanService,
        bot_client: DiscordBotClient | None = None,
    ) -> None:
        """Initialize the workflow with required V1 services."""

        self._user_list_service = user_list_service
        self._high_risk_guild_service = high_risk_guild_service
        self._verification_log_service = verification_log_service
        self._verification_decision_service = verification_decision_service
        self._guild_ban_service = guild_ban_service
        self._bot_client = bot_client

    async def verify(
        self,
        *,
        configuration: ConfigurationView,
        request: VerificationRequest,
        lang: str = "en",
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

        matched_high_risk_guild_ids = tuple(
            sorted(request.matched_high_risk_guild_ids)
        )
        high_risk_guild_detected = bool(matched_high_risk_guild_ids)

        shared_ip_detected = False
        if configuration.deny_shared_ip:
            shared_ip_detected = await self._verification_log_service.has_shared_ip(
                guild_id=request.guild_id,
                discord_user_id=request.discord_user_id,
                ip_address=request.ip_address,
            )

        matched_banned_user_ids = tuple(
            sorted(
                await self._guild_ban_service.find_banned_users_with_ip(
                    guild_id=request.guild_id,
                    discord_user_id=request.discord_user_id,
                    ip_address=request.ip_address,
                )
            )
        )
        banned_ip_match_detected = bool(matched_banned_user_ids)

        decision = self._verification_decision_service.evaluate(
            signals=VerificationSignals(
                whitelisted=whitelisted,
                user_blacklisted=user_blacklisted,
                vpn_or_proxy_detected=request.vpn_or_proxy_detected,
                shared_ip_detected=shared_ip_detected,
                discord_account_age_days=(request.discord_account_age_days),
                high_risk_guild_detected=high_risk_guild_detected,
                membership_check_unavailable=request.membership_check_unavailable,
                banned_ip_match_detected=banned_ip_match_detected,
                risk_provider_unavailable=request.risk_provider_unavailable,
            ),
            policy=VerificationPolicy(
                minimum_account_age_days=(configuration.minimum_account_age_days),
                deny_vpn_or_proxy=configuration.deny_vpn_or_proxy,
                deny_shared_ip=configuration.deny_shared_ip,
                vpn_or_proxy_action=configuration.vpn_or_proxy_action,
                shared_ip_action=configuration.shared_ip_action,
            ),
        )

        review_evidence: ReviewEvidence | None = None
        if decision.manual_review:
            high_risk_entries = await self._high_risk_guild_service.list_entries(
                request.guild_id
            )
            reason_by_id = {
                entry.high_risk_discord_guild_id: entry.reason
                for entry in high_risk_entries
            }
            matched_high_risk_servers = [
                MatchedHighRiskServerEvidence(
                    discord_guild_id=guild_id,
                    description=reason_by_id.get(guild_id),
                )
                for guild_id in matched_high_risk_guild_ids
            ]
            ban_snapshots = await self._guild_ban_service.get_ban_snapshots(
                guild_id=request.guild_id,
                discord_user_ids=list(matched_banned_user_ids),
            )
            matched_banned_accounts = await resolve_banned_account_identities(
                discord_guild_id=request.discord_guild_id,
                matched_user_ids=list(matched_banned_user_ids),
                ban_snapshots=ban_snapshots,
                bot_client=self._bot_client,
                lang=lang,
            )
            captured_at = datetime.now(timezone.utc)
            review_evidence = ReviewEvidence(
                reasons=derive_manual_review_reason_codes(
                    vpn_or_proxy_detected=request.vpn_or_proxy_detected,
                    shared_ip_detected=shared_ip_detected,
                    banned_ip_match_detected=banned_ip_match_detected,
                    high_risk_guild_detected=high_risk_guild_detected,
                    membership_check_unavailable=request.membership_check_unavailable,
                    risk_provider_unavailable=request.risk_provider_unavailable,
                ),
                matched_banned_accounts=matched_banned_accounts,
                matched_high_risk_servers=matched_high_risk_servers,
                proxy_classification=request.proxy_classification,
                evidence_captured_at=captured_at,
            )

        attempt = await self._verification_log_service.create_log(
            guild_id=request.guild_id,
            discord_user_id=request.discord_user_id,
            status=_OUTCOME_TO_STATUS[decision.outcome],
            reason=decision.reason.value,
            ip_address=request.ip_address,
            vpn_or_proxy_detected=request.vpn_or_proxy_detected,
            shared_ip_detected=shared_ip_detected,
            high_risk_guild_detected=high_risk_guild_detected,
            matched_high_risk_guild_ids=list(matched_high_risk_guild_ids),
            banned_ip_match_detected=banned_ip_match_detected,
            matched_banned_user_ids=list(matched_banned_user_ids),
            review_evidence=(
                review_evidence.model_dump(mode="json") if review_evidence else None
            ),
        )

        return VerificationResult(
            allowed=decision.allowed,
            manual_review=decision.manual_review,
            reason=decision.reason,
            shared_ip_detected=shared_ip_detected,
            high_risk_guild_detected=high_risk_guild_detected,
            matched_high_risk_guild_ids=matched_high_risk_guild_ids,
            banned_ip_match_detected=banned_ip_match_detected,
            matched_banned_user_ids=matched_banned_user_ids,
            review_evidence=review_evidence,
            attempt_id=attempt.id,
            created_at=attempt.created_at,
        )


__all__ = [
    "VerificationRequest",
    "VerificationResult",
    "VerificationService",
]
