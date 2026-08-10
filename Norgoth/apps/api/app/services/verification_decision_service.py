"""Verification decision rules for Discord users.

The engine returns a three-state outcome — ``ALLOW``, ``DENY`` or
``MANUAL_REVIEW`` — evaluated in a deterministic, order-independent precedence:

1. Whitelisted            -> ALLOW (full override; bypasses every risk rule)
2. User blacklisted       -> DENY
3. VPN/proxy  (enabled + detected + action=DENY)  -> DENY
4. Shared IP  (enabled + detected + action=DENY)  -> DENY
5. Account too new        -> DENY
6. VPN/proxy  (enabled + detected + action=MANUAL_REVIEW) -> MANUAL_REVIEW
7. Shared IP  (enabled + detected + action=MANUAL_REVIEW) -> MANUAL_REVIEW
8. High-risk-guild member -> MANUAL_REVIEW
9. Otherwise              -> ALLOW

Each detector carries a configurable action (``deny`` or ``manual_review``); a
DENY from any enabled detector always outranks a MANUAL_REVIEW. High-risk-guild
membership always routes to human review. The single ``reason`` returned is the
primary code; callers surface every triggered signal from the persisted booleans.
Integrity/OAuth failures are handled upstream in the callback and never reach
this engine; whitelist only overrides the risk rules above, not those.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.models.enums import RiskAction


class VerificationOutcome(StrEnum):
    """Three-state result of a verification evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    MANUAL_REVIEW = "manual_review"


class VerificationDecisionReason(StrEnum):
    """Supported final reasons for a verification decision."""

    ALLOWED = "allowed"
    WHITELISTED = "whitelisted"
    USER_BLACKLISTED = "user_blacklisted"
    VPN_OR_PROXY_DETECTED = "vpn_or_proxy_detected"
    SHARED_IP_DETECTED = "shared_ip_detected"
    ACCOUNT_TOO_NEW = "account_too_new"
    HIGH_RISK_GUILD = "high_risk_guild"


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    """Final result of a Discord verification evaluation."""

    outcome: VerificationOutcome
    reason: VerificationDecisionReason

    @property
    def allowed(self) -> bool:
        """Return whether the attempt is auto-approved (ALLOW only)."""

        return self.outcome is VerificationOutcome.ALLOW

    @property
    def manual_review(self) -> bool:
        """Return whether the attempt requires human review."""

        return self.outcome is VerificationOutcome.MANUAL_REVIEW


@dataclass(frozen=True, slots=True)
class VerificationSignals:
    """Inputs required to evaluate one verification attempt."""

    whitelisted: bool
    user_blacklisted: bool
    vpn_or_proxy_detected: bool
    shared_ip_detected: bool
    discord_account_age_days: int
    high_risk_guild_detected: bool = False


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    """Guild-controlled verification settings.

    ``deny_vpn_or_proxy`` / ``deny_shared_ip`` are the detector ENABLED flags;
    the ``*_action`` fields decide whether a firing detector denies or routes to
    manual review. Actions default to ``DENY`` to preserve legacy behavior.
    """

    minimum_account_age_days: int
    deny_vpn_or_proxy: bool
    deny_shared_ip: bool
    vpn_or_proxy_action: RiskAction = RiskAction.DENY
    shared_ip_action: RiskAction = RiskAction.DENY


class VerificationDecisionService:
    """Evaluate Discord verification attempts using V1 rules."""

    def evaluate(
        self,
        *,
        signals: VerificationSignals,
        policy: VerificationPolicy,
    ) -> VerificationDecision:
        """Return the final allow / deny / manual-review decision."""

        if signals.whitelisted:
            return VerificationDecision(
                outcome=VerificationOutcome.ALLOW,
                reason=VerificationDecisionReason.WHITELISTED,
            )

        # A detector "fires" only when it is enabled AND its signal is present.
        vpn_fires = policy.deny_vpn_or_proxy and signals.vpn_or_proxy_detected
        shared_fires = policy.deny_shared_ip and signals.shared_ip_detected

        # --- DENY tier (a DENY from any source outranks manual review) --------
        if signals.user_blacklisted:
            return VerificationDecision(
                outcome=VerificationOutcome.DENY,
                reason=VerificationDecisionReason.USER_BLACKLISTED,
            )

        if vpn_fires and policy.vpn_or_proxy_action is RiskAction.DENY:
            return VerificationDecision(
                outcome=VerificationOutcome.DENY,
                reason=VerificationDecisionReason.VPN_OR_PROXY_DETECTED,
            )

        if shared_fires and policy.shared_ip_action is RiskAction.DENY:
            return VerificationDecision(
                outcome=VerificationOutcome.DENY,
                reason=VerificationDecisionReason.SHARED_IP_DETECTED,
            )

        if signals.discord_account_age_days < policy.minimum_account_age_days:
            return VerificationDecision(
                outcome=VerificationOutcome.DENY,
                reason=VerificationDecisionReason.ACCOUNT_TOO_NEW,
            )

        # --- MANUAL_REVIEW tier (primary reason follows this fixed order) -----
        if vpn_fires and policy.vpn_or_proxy_action is RiskAction.MANUAL_REVIEW:
            return VerificationDecision(
                outcome=VerificationOutcome.MANUAL_REVIEW,
                reason=VerificationDecisionReason.VPN_OR_PROXY_DETECTED,
            )

        if shared_fires and policy.shared_ip_action is RiskAction.MANUAL_REVIEW:
            return VerificationDecision(
                outcome=VerificationOutcome.MANUAL_REVIEW,
                reason=VerificationDecisionReason.SHARED_IP_DETECTED,
            )

        if signals.high_risk_guild_detected:
            return VerificationDecision(
                outcome=VerificationOutcome.MANUAL_REVIEW,
                reason=VerificationDecisionReason.HIGH_RISK_GUILD,
            )

        return VerificationDecision(
            outcome=VerificationOutcome.ALLOW,
            reason=VerificationDecisionReason.ALLOWED,
        )


__all__ = [
    "VerificationDecision",
    "VerificationDecisionReason",
    "VerificationDecisionService",
    "VerificationOutcome",
    "VerificationPolicy",
    "VerificationSignals",
]
