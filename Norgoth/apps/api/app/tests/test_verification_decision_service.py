"""Tests for Discord verification decision rules."""

from app.services.verification_decision_service import (
    VerificationDecisionReason,
    VerificationDecisionService,
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
        blacklisted_guild_detected=False,
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
        blacklisted_guild_detected=True,
        vpn_or_proxy_detected=True,
        shared_ip_detected=True,
        discord_account_age_days=0,
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
        blacklisted_guild_detected=False,
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


def test_rejects_member_of_blacklisted_guild() -> None:
    """Membership in a blocked Discord guild should reject verification."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        blacklisted_guild_detected=True,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        discord_account_age_days=365,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.BLACKLISTED_GUILD


def test_rejects_vpn_or_proxy_when_enabled() -> None:
    """VPN or proxy use should be rejected when protection is enabled."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=False,
        blacklisted_guild_detected=False,
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
        blacklisted_guild_detected=False,
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
        blacklisted_guild_detected=False,
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
        blacklisted_guild_detected=False,
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
        blacklisted_guild_detected=False,
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
        blacklisted_guild_detected=False,
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


def test_user_blacklist_precedes_network_checks() -> None:
    """Manual user blacklist should remain the primary denial reason."""

    service = VerificationDecisionService()

    signals = VerificationSignals(
        whitelisted=False,
        user_blacklisted=True,
        blacklisted_guild_detected=True,
        vpn_or_proxy_detected=True,
        shared_ip_detected=True,
        discord_account_age_days=0,
    )

    decision = service.evaluate(
        signals=signals,
        policy=_default_policy(),
    )

    assert decision.allowed is False
    assert decision.reason is VerificationDecisionReason.USER_BLACKLISTED
