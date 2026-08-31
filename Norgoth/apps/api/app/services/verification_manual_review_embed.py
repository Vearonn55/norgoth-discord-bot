"""Build localized manual-review Discord log embed payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.review_evidence import ReviewEvidence
from app.services.logging_presentation import (
    apply_log_title_emoji,
    filter_log_embed_fields,
)
from app.services.verification_i18n import (
    additional_details_notice,
    build_reason_lines,
    manual_review_title,
    open_manual_verification_label,
    reasons_field_name,
    truncate_utf8,
)
from app.services.verification_log_routing import classification_to_event_type


def build_manual_verification_dashboard_url(
    *,
    dashboard_public_url: str | None,
    discord_guild_id: str,
    attempt_id: UUID,
    lang: str = "en",
) -> str | None:
    """Return a deep link to the manual verification review page."""

    if not dashboard_public_url:
        return None
    base = dashboard_public_url.rstrip("/")
    locale = "tr" if lang.lower().startswith("tr") else "en"
    return (
        f"{base}/{locale}/community/manual-verification/reviews/"
        f"{attempt_id}?g={discord_guild_id}"
    )


def build_manual_review_log_payload(
    *,
    lang: str,
    discord_guild_id: str,
    user_id: str,
    username: str,
    review_role_id: str,
    attempt_id: UUID,
    created_at: datetime,
    dashboard_public_url: str | None,
    review_evidence: ReviewEvidence | None,
    vpn_or_proxy_detected: bool,
    shared_ip_detected: bool,
    banned_ip_match_detected: bool,
    high_risk_guild_detected: bool,
    membership_check_unavailable: bool,
    risk_provider_unavailable: bool,
) -> dict[str, object]:
    """Assemble the Discord message payload for a manual-review log."""

    event_type = classification_to_event_type(
        allowed=False,
        manual_review=True,
        role_grant_failed=False,
    )
    title = apply_log_title_emoji(event_type, manual_review_title(lang))

    reason_lines = build_reason_lines(
        lang=lang,
        evidence=review_evidence,
        vpn_or_proxy_detected=vpn_or_proxy_detected,
        shared_ip_detected=shared_ip_detected,
        banned_ip_match_detected=banned_ip_match_detected,
        high_risk_guild_detected=high_risk_guild_detected,
        membership_check_unavailable=membership_check_unavailable,
        risk_provider_unavailable=risk_provider_unavailable,
    )
    reasons_value = "\n".join(reason_lines) if reason_lines else "—"
    truncated = truncate_utf8(reasons_value, 900)
    if truncated != reasons_value:
        truncated = f"{truncated}\n{additional_details_notice(lang)}"

    content = None
    allowed_roles: list[str] = []
    if review_role_id:
        content = f"<@&{review_role_id}>"
        allowed_roles = [review_role_id]

    embed = {
        "title": title,
        "color": 0xFBBF24,
        "timestamp": created_at.isoformat(),
        "footer": {"text": f"Attempt {attempt_id}"},
        "fields": filter_log_embed_fields(
            [
                {
                    "name": "User",
                    "value": f"<@{user_id}> (`{user_id}`)",
                    "inline": False,
                },
                {
                    "name": "Display",
                    "value": username[:80] or "—",
                    "inline": True,
                },
                {
                    "name": reasons_field_name(lang),
                    "value": truncate_utf8(truncated, 1024),
                    "inline": False,
                },
            ]
        ),
    }

    payload: dict[str, object] = {
        "embeds": [embed],
        "allowed_mentions": {"parse": [], "roles": allowed_roles},
    }
    if content:
        payload["content"] = content

    dashboard_url = build_manual_verification_dashboard_url(
        dashboard_public_url=dashboard_public_url,
        discord_guild_id=discord_guild_id,
        attempt_id=attempt_id,
        lang=lang,
    )
    if dashboard_url:
        payload["components"] = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": open_manual_verification_label(lang),
                        "url": dashboard_url,
                    }
                ],
            }
        ]

    return payload
