"""Localized strings for verification moderator Discord embeds."""

from __future__ import annotations

from app.schemas.review_evidence import BannedAccountEvidence, ReviewEvidence


def _pick(lang: str, *, en: str, tr: str) -> str:
    return tr if lang.lower().startswith("tr") else en


def manual_review_title(lang: str) -> str:
    return _pick(lang, en="Manual Review Required", tr="Manuel İnceleme Gerekli")


def open_manual_verification_label(lang: str) -> str:
    return _pick(
        lang,
        en="📋 Open Manual Verification",
        tr="📋 Manuel Doğrulamayı Aç",
    )


def reasons_field_name(lang: str) -> str:
    return _pick(lang, en="Reasons", tr="Nedenler")


def additional_details_notice(lang: str) -> str:
    return _pick(
        lang,
        en="See the dashboard for full details.",
        tr="Tüm ayrıntılar için panele bakın.",
    )


def unavailable_discord_user_label(*, lang: str, user_id: str) -> str:
    prefix = _pick(
        lang,
        en="Unavailable user",
        tr="Kullanılamayan kullanıcı",
    )
    return f"{prefix} — User ID: {user_id}"


def format_banned_account(
    *,
    lang: str,
    account: BannedAccountEvidence,
) -> str:
    if account.username and account.display_name:
        template = _pick(
            lang,
            en="{display} (@{username}) — User ID: {id}",
            tr="{display} (@{username}) — Kullanıcı ID: {id}",
        )
        return template.format(
            display=account.display_name,
            username=account.username,
            id=account.discord_user_id,
        )
    if account.display_name:
        template = _pick(
            lang,
            en="{display} — User ID: {id}",
            tr="{display} — Kullanıcı ID: {id}",
        )
        return template.format(display=account.display_name, id=account.discord_user_id)
    return unavailable_discord_user_label(lang=lang, user_id=account.discord_user_id)


def reason_line_vpn_or_proxy(lang: str, *, classification: str | None) -> str:
    if classification:
        template = _pick(
            lang,
            en="VPN / Proxy detected ({classification})",
            tr="VPN / Proxy tespit edildi ({classification})",
        )
        return template.format(classification=classification)
    return _pick(
        lang,
        en="VPN / Proxy detected",
        tr="VPN / Proxy tespit edildi",
    )


def reason_line_shared_ip(lang: str) -> str:
    return _pick(
        lang,
        en="Shared IP / possible alternate account",
        tr="Paylaşılan IP / olası ikincil hesap",
    )


def reason_line_banned_ip_match(lang: str, *, accounts: list[BannedAccountEvidence]) -> str:
    heading = _pick(
        lang,
        en="Possible ban evasion (matched banned account IP)",
        tr="Olası ban kaçırma (yasaklı hesap IP eşleşmesi)",
    )
    if not accounts:
        return heading
    lines = [heading]
    for account in accounts:
        lines.append(f"• {format_banned_account(lang=lang, account=account)}")
    return "\n".join(lines)


def reason_line_high_risk_server(
    lang: str,
    *,
    discord_guild_id: str,
    description: str | None,
) -> str:
    if description:
        template = _pick(
            lang,
            en="High Risk Server: {id} — {description}",
            tr="Yüksek Riskli Sunucu: {id} — {description}",
        )
        return template.format(id=discord_guild_id, description=description)
    template = _pick(
        lang,
        en="High Risk Server: {id}",
        tr="Yüksek Riskli Sunucu: {id}",
    )
    return template.format(id=discord_guild_id)


def reason_line_membership_unavailable(lang: str) -> str:
    return _pick(
        lang,
        en="Server membership check unavailable",
        tr="Sunucu üyeliği doğrulaması kullanılamıyor",
    )


def reason_line_risk_provider_unavailable(lang: str) -> str:
    return _pick(
        lang,
        en="VPN / Proxy risk check unavailable",
        tr="VPN / Proxy risk kontrolü kullanılamıyor",
    )


def build_reason_lines(
    *,
    lang: str,
    evidence: ReviewEvidence | None,
    vpn_or_proxy_detected: bool,
    shared_ip_detected: bool,
    banned_ip_match_detected: bool,
    high_risk_guild_detected: bool,
    membership_check_unavailable: bool,
    risk_provider_unavailable: bool,
) -> list[str]:
    """Build localized reason lines for moderator embeds."""

    lines: list[str] = []
    proxy_classification = evidence.proxy_classification if evidence else None
    banned_accounts = evidence.matched_banned_accounts if evidence else []
    hr_servers = evidence.matched_high_risk_servers if evidence else []

    if vpn_or_proxy_detected:
        lines.append(
            reason_line_vpn_or_proxy(lang, classification=proxy_classification)
        )
    if shared_ip_detected:
        lines.append(reason_line_shared_ip(lang))
    if banned_ip_match_detected:
        lines.append(
            reason_line_banned_ip_match(lang, accounts=list(banned_accounts))
        )
    if high_risk_guild_detected:
        if hr_servers:
            for server in hr_servers:
                lines.append(
                    reason_line_high_risk_server(
                        lang,
                        discord_guild_id=server.discord_guild_id,
                        description=server.description,
                    )
                )
        else:
            lines.append(
                reason_line_high_risk_server(
                    lang,
                    discord_guild_id="—",
                    description=None,
                )
            )
    if membership_check_unavailable:
        lines.append(reason_line_membership_unavailable(lang))
    if risk_provider_unavailable:
        lines.append(reason_line_risk_provider_unavailable(lang))
    return lines


def truncate_utf8(text: str, max_bytes: int) -> str:
    """Truncate text to a UTF-8 byte budget without splitting code points."""

    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    trimmed = encoded[:max_bytes]
    while trimmed:
        try:
            return trimmed.decode("utf-8")
        except UnicodeDecodeError:
            trimmed = trimmed[:-1]
    return ""
