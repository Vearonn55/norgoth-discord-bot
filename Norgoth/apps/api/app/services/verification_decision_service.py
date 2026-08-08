"""Verification decision rules for Discord users."""

from dataclasses import dataclass
from enum import StrEnum


class VerificationDecisionReason(StrEnum):
    """Supported final reasons for a verification decision."""

    ALLOWED = "allowed"
    WHITELISTED = "whitelisted"
    USER_BLACKLISTED = "user_blacklisted"
    BLACKLISTED_GUILD = "blacklisted_guild"
    VPN_OR_PROXY_DETECTED = "vpn_or_proxy_detected"
    SHARED_IP_DETECTED = "shared_ip_detected"
    ACCOUNT_TOO_NEW = "account_too_new"


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    """Final result of a Discord verification evaluation."""

    allowed: bool
    reason: VerificationDecisionReason


@dataclass(frozen=True, slots=True)
class VerificationSignals:
    """Inputs required to evaluate one verification attempt."""

    whitelisted: bool
    user_blacklisted: bool
    blacklisted_guild_detected: bool
    vpn_or_proxy_detected: bool
    shared_ip_detected: bool
    discord_account_age_days: int


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    """Guild-controlled verification settings."""

    minimum_account_age_days: int
    deny_vpn_or_proxy: bool
    deny_shared_ip: bool


class VerificationDecisionService:
    """Evaluate Discord verification attempts using V1 rules."""

    def evaluate(
        self,
        *,
        signals: VerificationSignals,
        policy: VerificationPolicy,
    ) -> VerificationDecision:
        """Return the final allow or deny decision."""

        if signals.whitelisted:
            return VerificationDecision(
                allowed=True,
                reason=VerificationDecisionReason.WHITELISTED,
            )

        if signals.user_blacklisted:
            return VerificationDecision(
                allowed=False,
                reason=VerificationDecisionReason.USER_BLACKLISTED,
            )

        if signals.blacklisted_guild_detected:
            return VerificationDecision(
                allowed=False,
                reason=VerificationDecisionReason.BLACKLISTED_GUILD,
            )

        if policy.deny_vpn_or_proxy and signals.vpn_or_proxy_detected:
            return VerificationDecision(
                allowed=False,
                reason=(VerificationDecisionReason.VPN_OR_PROXY_DETECTED),
            )

        if policy.deny_shared_ip and signals.shared_ip_detected:
            return VerificationDecision(
                allowed=False,
                reason=VerificationDecisionReason.SHARED_IP_DETECTED,
            )

        if signals.discord_account_age_days < policy.minimum_account_age_days:
            return VerificationDecision(
                allowed=False,
                reason=VerificationDecisionReason.ACCOUNT_TOO_NEW,
            )

        return VerificationDecision(
            allowed=True,
            reason=VerificationDecisionReason.ALLOWED,
        )


__all__ = [
    "VerificationDecision",
    "VerificationDecisionReason",
    "VerificationDecisionService",
    "VerificationPolicy",
    "VerificationSignals",
]
