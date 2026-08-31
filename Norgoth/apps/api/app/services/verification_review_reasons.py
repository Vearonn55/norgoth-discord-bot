"""Derive normalized manual-review reason codes from attempt signals."""

from __future__ import annotations

from app.services.verification_decision_service import VerificationDecisionReason


def derive_manual_review_reason_codes(
    *,
    vpn_or_proxy_detected: bool,
    shared_ip_detected: bool,
    banned_ip_match_detected: bool,
    high_risk_guild_detected: bool,
    membership_check_unavailable: bool,
    risk_provider_unavailable: bool,
) -> list[str]:
    """Return every triggered manual-review reason in stable display order."""

    codes: list[str] = []
    if vpn_or_proxy_detected:
        codes.append("vpn_or_proxy")
    if shared_ip_detected:
        codes.append("shared_ip")
    if banned_ip_match_detected:
        codes.append("banned_ip_match")
    if high_risk_guild_detected:
        codes.append("high_risk_server")
    if membership_check_unavailable:
        codes.append("membership_check_unavailable")
    if risk_provider_unavailable:
        codes.append("risk_provider_unavailable")
    return codes


def decision_reason_to_review_code(reason: VerificationDecisionReason) -> str | None:
    """Map a primary decision reason to a dashboard reason code."""

    mapping = {
        VerificationDecisionReason.VPN_OR_PROXY_DETECTED: "vpn_or_proxy",
        VerificationDecisionReason.SHARED_IP_DETECTED: "shared_ip",
        VerificationDecisionReason.BANNED_IP_MATCH: "banned_ip_match",
        VerificationDecisionReason.HIGH_RISK_GUILD: "high_risk_server",
        VerificationDecisionReason.MEMBERSHIP_CHECK_UNAVAILABLE: (
            "membership_check_unavailable"
        ),
        VerificationDecisionReason.RISK_PROVIDER_UNAVAILABLE: (
            "risk_provider_unavailable"
        ),
    }
    return mapping.get(reason)
