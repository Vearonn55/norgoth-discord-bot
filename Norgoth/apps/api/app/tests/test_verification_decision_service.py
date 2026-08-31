"""Tests for Discord verification decision rules."""

from app.models.enums import RiskAction
from app.services.verification_decision_service import (
    VerificationDecisionReason,
    VerificationDecisionService,
    VerificationOutcome,
    VerificationPolicy,
    VerificationSignals,
)


def _default_policy() -> VerificationPolicy:
    """Return the default V1 verification policy."""

    return VerificationPolicy(
        minimum_account_age_days=30,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
    )


def _safe_signals() -> VerificationSignals:
    """Return signals representing a normal verification attempt."""

    return VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=365,
    )


def test_allows_safe_verification() -> None:
    """A user with no blocked signals should be allowed."""

    service = VerificationDecisionService()

    decision = service.evaluate(
        signals=_safe_signals(),
        policy=_default_policy(),
    )

    assert decision.allowed is True
    assert decision.reason is VerificationDecisionReason.ALLOWED


def test_whitelist_allows_user_before_other_checks() -> None:
    """A whitelisted user should bypass remaining V1 checks."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=True,
        user_blacklisted=True,
        vpn_or_proxy_detected=True,
        shared_ip_detected=True,
        discord_account_age_days=0,
        high_risk_guild_detected=True,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is True
    assert decision.reason is VerificationDecisionReason.WHITELISTED


def test_rejects_blacklisted_user() -> None:
    """A manually blacklisted Discord user should be rejected."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=True,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=365,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.USER_BLACKLISTED


def test_high_risk_guild_routes_to_manual_review() -> None:
    """Membership in a high-risk guild should route to manual review.

    This replaces the legacy Blacklisted-Guild hard rejection: a former
    blacklisted guild is now a High Risk Server and triggers human review
    instead of an automatic deny.
    """

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=365,
        high_risk_guild_detected=True,
    )

    decision = service.evaluate(signals=signals, policy=_default_policy())

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.manual_review is True
    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.HIGH_RISK_GUILD


def test_whitelist_overrides_high_risk_guild() -> None:
    """A whitelisted user bypasses high-risk manual review (full override)."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=True,
        user_blacklisted=False,
        vpn_or_proxy_detected=True,
        shared_ip_detected=True,
        discord_account_age_days=0,
        high_risk_guild_detected=True,
    )

    decision = service.evaluate(signals=signals, policy=_default_policy())

    assert decision.outcome is VerificationOutcome.ALLOW
    assert decision.reason is VerificationDecisionReason.WHITELISTED


def test_hard_deny_precedes_high_risk_manual_review() -> None:
    """A blocking deny rule takes precedence over high-risk manual review."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=True,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=365,
        high_risk_guild_detected=True,
    )

    decision = service.evaluate(signals=signals, policy=_default_policy())

    assert decision.outcome is VerificationOutcome.DENY
    assert decision.reason is VerificationDecisionReason.USER_BLACKLISTED


def test_vpn_deny_precedes_high_risk_manual_review() -> None:
    """A VPN deny outranks high-risk manual review."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=True,
        shared_ip_detected=False,
        discord_account_age_days=365,
        high_risk_guild_detected=True,
    )

    decision = service.evaluate(signals=signals, policy=_default_policy())

    assert decision.outcome is VerificationOutcome.DENY
    assert decision.reason is VerificationDecisionReason.VPN_OR_PROXY_DETECTED


def test_rejects_vpn_or_proxy_when_enabled() -> None:
    """VPN or proxy use should be rejected when protection is enabled."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=True,
        shared_ip_detected=False,
        discord_account_age_days=365,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.VPN_OR_PROXY_DETECTED


def test_allows_vpn_or_proxy_when_disabled() -> None:
    """VPN or proxy use should not block when protection is disabled."""

    service = VerificationDecisionService()

    policy = VerificationPolicy(
        minimum_account_age_days=30,
        deny_vpn_or_proxy=False,
        deny_shared_ip=True,
    )

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=True,
        shared_ip_detected=False,
        discord_account_age_days=365,
    )

    decision = service.evaluate(
        signals=signals,
        policy=policy,
    )

    assert decision.allowed is True
    assert decision.reason is VerificationDecisionReason.ALLOWED


def test_rejects_shared_ip_when_enabled() -> None:
    """A shared IP should reject verification when protection is enabled."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=False,
        shared_ip_detected=True,
        discord_account_age_days=365,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.SHARED_IP_DETECTED


def test_allows_shared_ip_when_disabled() -> None:
    """A shared IP should not block when protection is disabled."""

    service = VerificationDecisionService()

    policy = VerificationPolicy(
        minimum_account_age_days=30,
        deny_vpn_or_proxy=True,
        deny_shared_ip=False,
    )

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=False,
        shared_ip_detected=True,
        discord_account_age_days=365,
    )

    decision = service.evaluate(
        signals=signals,
        policy=policy,
    )

    assert decision.allowed is True
    assert decision.reason is VerificationDecisionReason.ALLOWED


def test_rejects_account_younger_than_minimum() -> None:
    """A Discord account below the age limit should be rejected."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=29,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.ACCOUNT_TOO_NEW


def test_allows_account_exactly_at_minimum_age() -> None:
    """An account exactly at the configured age should be allowed."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=30,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is True
    assert decision.reason is VerificationDecisionReason.ALLOWED


def test_no_blacklisted_guild_reason_exists() -> None:
    """The legacy Blacklisted-Guild rejection reason must be gone."""

    assert not hasattr(VerificationDecisionReason, "BLACKLISTED_GUILD")
    assert "blacklisted_guild" not in {
        reason.value for reason in VerificationDecisionReason
    }


# --- Configurable risk-action routing matrix --------------------------------


def _policy(
    *,
    vpn_enabled: bool = True,
    shared_enabled: bool = True,
    vpn_action: RiskAction = RiskAction.DENY,
    shared_action: RiskAction = RiskAction.DENY,
) -> VerificationPolicy:
    """Build a policy with explicit detector enabled flags and actions."""

    return VerificationPolicy(
        minimum_account_age_days=30,
        deny_vpn_or_proxy=vpn_enabled,
        deny_shared_ip=shared_enabled,
        vpn_or_proxy_action=vpn_action,
        shared_ip_action=shared_action,
    )


def test_vpn_manual_action_routes_to_manual_review() -> None:
    """VPN detection with a MANUAL_REVIEW action routes to review, not deny."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=True,
            shared_ip_detected=False,
            discord_account_age_days=365,
        ),
        policy=_policy(vpn_action=RiskAction.MANUAL_REVIEW),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.VPN_OR_PROXY_DETECTED


def test_shared_ip_manual_action_routes_to_manual_review() -> None:
    """Shared IP with a MANUAL_REVIEW action routes to review, not deny."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=True,
            discord_account_age_days=365,
        ),
        policy=_policy(shared_action=RiskAction.MANUAL_REVIEW),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.SHARED_IP_DETECTED


def test_deny_outranks_manual_across_detectors() -> None:
    """A DENY from one detector outranks a MANUAL_REVIEW from another."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=True,
            shared_ip_detected=True,
            discord_account_age_days=365,
        ),
        policy=_policy(
            vpn_action=RiskAction.DENY,
            shared_action=RiskAction.MANUAL_REVIEW,
        ),
    )

    assert decision.outcome is VerificationOutcome.DENY
    assert decision.reason is VerificationDecisionReason.VPN_OR_PROXY_DETECTED


def test_both_manual_returns_manual_with_vpn_primary() -> None:
    """Two MANUAL_REVIEW detectors yield MANUAL with VPN as primary reason."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=True,
            shared_ip_detected=True,
            discord_account_age_days=365,
        ),
        policy=_policy(
            vpn_action=RiskAction.MANUAL_REVIEW,
            shared_action=RiskAction.MANUAL_REVIEW,
        ),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.VPN_OR_PROXY_DETECTED


def test_disabled_vpn_lets_shared_manual_route_review() -> None:
    """A disabled VPN detector cannot affect the shared-IP manual outcome."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=True,
            shared_ip_detected=True,
            discord_account_age_days=365,
        ),
        policy=_policy(
            vpn_enabled=False,
            vpn_action=RiskAction.DENY,
            shared_action=RiskAction.MANUAL_REVIEW,
        ),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.SHARED_IP_DETECTED


def test_shared_deny_outranks_high_risk_manual() -> None:
    """A shared-IP DENY outranks high-risk manual review."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=True,
            discord_account_age_days=365,
            high_risk_guild_detected=True,
        ),
        policy=_policy(shared_action=RiskAction.DENY),
    )

    assert decision.outcome is VerificationOutcome.DENY
    assert decision.reason is VerificationDecisionReason.SHARED_IP_DETECTED


def test_whitelist_bypasses_configurable_detectors() -> None:
    """Whitelisted users bypass VPN/Shared-IP regardless of action config."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=True,
            user_blacklisted=False,
            vpn_or_proxy_detected=True,
            shared_ip_detected=True,
            discord_account_age_days=0,
            high_risk_guild_detected=True,
        ),
        policy=_policy(
            vpn_action=RiskAction.MANUAL_REVIEW,
            shared_action=RiskAction.MANUAL_REVIEW,
        ),
    )

    assert decision.outcome is VerificationOutcome.ALLOW
    assert decision.reason is VerificationDecisionReason.WHITELISTED


def test_membership_check_unavailable_routes_to_manual_review() -> None:
    """When guild membership cannot be verified, route to manual review."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=False,
            discord_account_age_days=365,
            high_risk_guild_detected=False,
            membership_check_unavailable=True,
        ),
        policy=_default_policy(),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.MEMBERSHIP_CHECK_UNAVAILABLE


def test_high_risk_precedes_membership_unavailable() -> None:
    """A confirmed high-risk match outranks unavailable lookup fallback."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=False,
            discord_account_age_days=365,
            high_risk_guild_detected=True,
            membership_check_unavailable=True,
        ),
        policy=_default_policy(),
    )

    assert decision.reason is VerificationDecisionReason.HIGH_RISK_GUILD


def test_banned_ip_match_routes_to_manual_review() -> None:
    """An active banned-account IP match routes to manual review."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=False,
            discord_account_age_days=365,
            banned_ip_match_detected=True,
        ),
        policy=_default_policy(),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.BANNED_IP_MATCH


def test_risk_provider_unavailable_routes_to_manual_review() -> None:
    """When proxycheck is unavailable, route to manual review."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=False,
            discord_account_age_days=365,
            risk_provider_unavailable=True,
        ),
        policy=_default_policy(),
    )

    assert decision.outcome is VerificationOutcome.MANUAL_REVIEW
    assert decision.reason is VerificationDecisionReason.RISK_PROVIDER_UNAVAILABLE


def test_banned_ip_match_precedes_high_risk_manual_review() -> None:
    """Banned IP match outranks high-risk manual review."""

    decision = VerificationDecisionService().evaluate(
        signals=VerificationSignals(
            whitelisted=False,
            user_blacklisted=False,
            vpn_or_proxy_detected=False,
            shared_ip_detected=False,
            discord_account_age_days=365,
            banned_ip_match_detected=True,
            high_risk_guild_detected=True,
        ),
        policy=_default_policy(),
    )

    assert decision.reason is VerificationDecisionReason.BANNED_IP_MATCH
