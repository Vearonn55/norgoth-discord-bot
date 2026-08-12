"""Public HTML pages for Member Verification (FastAPI, not Next.js)."""

from __future__ import annotations

import html

from app.services.guild_meta import guild_initials

BRAND = "NorBot Verification"

COPY: dict[str, dict[str, str]] = {
    "en": {
        "unavailable_title": "Verification unavailable",
        "complete_title": "Verification complete",
        "pending_title": "Verification pending review",
        "denied_title": "Verification denied",
        "role_pending_title": "Verified — role pending",
        "not_configured": (
            "Verification is not configured for this server. "
            "Please contact a server administrator."
        ),
        "incomplete": (
            "Verification setup is incomplete for this server. "
            "Please contact a server administrator."
        ),
        "disabled": (
            "Verification is currently disabled for this server. "
            "Please contact a server administrator."
        ),
        "degraded": (
            "Verification Discord resources are missing or the bot "
            "cannot manage them. Please contact a server administrator."
        ),
        "error": (
            "Discord is temporarily unavailable. Please try again shortly."
        ),
        "guild_not_found": "This verification link is invalid or outdated.",
        "oauth_denied": "Discord authorization was cancelled. You can close this tab.",
        "oauth_invalid": "This verification link expired or is invalid. Open the link from Discord again.",
        "not_in_guild": "You must be a member of this Discord server to verify.",
        "retry": "Retry",
        "contact_admins": "Contact a server administrator for help.",
        "complete_detail": (
            "Welcome, {username}. You now have access to {guild}. "
            "You can close this tab and return to Discord."
        ),
        "pending_detail": (
            "Thanks, {username}. Your access to {guild} is pending manual "
            "review by the moderation team. You can close this tab."
        ),
        "denied_detail": (
            "Sorry, {username}. Access to {guild} was denied: {reason}"
        ),
        "role_pending_detail": (
            "Thanks, {username}. You passed verification for {guild}, but "
            "the bot could not update your Discord roles yet. Contact a "
            "server administrator if access does not appear shortly."
        ),
        "allowed": "You passed all verification checks.",
        "whitelisted": "You are on this server's whitelist.",
        "user_blacklisted": "You are blacklisted on this server.",
        "vpn_or_proxy_detected": "A VPN or proxy connection was detected.",
        "shared_ip_detected": "Your connection matches another verified account.",
        "account_too_new": "Your Discord account is too new for this server.",
        "high_risk_guild": "Your account is being reviewed by the moderation team.",
    },
    "tr": {
        "unavailable_title": "Doğrulama kullanılamıyor",
        "complete_title": "Doğrulama tamamlandı",
        "pending_title": "Doğrulama inceleme bekliyor",
        "denied_title": "Doğrulama reddedildi",
        "role_pending_title": "Doğrulandı — rol bekleniyor",
        "not_configured": (
            "Bu sunucu için doğrulama yapılandırılmamış. "
            "Lütfen bir sunucu yöneticisine başvurun."
        ),
        "incomplete": (
            "Bu sunucu için doğrulama kurulumu tamamlanmamış. "
            "Lütfen bir sunucu yöneticisine başvurun."
        ),
        "disabled": (
            "Bu sunucu için doğrulama şu anda kapalı. "
            "Lütfen bir sunucu yöneticisine başvurun."
        ),
        "degraded": (
            "Doğrulama Discord kaynakları eksik veya bot bunları "
            "yönetemiyor. Lütfen bir sunucu yöneticisine başvurun."
        ),
        "error": (
            "Discord geçici olarak kullanılamıyor. Lütfen kısa süre sonra yeniden deneyin."
        ),
        "guild_not_found": "Bu doğrulama bağlantısı geçersiz veya güncel değil.",
        "oauth_denied": "Discord yetkilendirmesi iptal edildi. Bu sekmeyi kapatabilirsiniz.",
        "oauth_invalid": "Bu doğrulama bağlantısının süresi dolmuş veya geçersiz. Discord’daki bağlantıyı yeniden açın.",
        "not_in_guild": "Doğrulamak için bu Discord sunucusunun üyesi olmalısınız.",
        "retry": "Yeniden dene",
        "contact_admins": "Yardım için bir sunucu yöneticisine başvurun.",
        "complete_detail": (
            "Hoş geldiniz, {username}. Artık {guild} sunucusuna erişiminiz var. "
            "Bu sekmeyi kapatıp Discord’a dönebilirsiniz."
        ),
        "pending_detail": (
            "Teşekkürler, {username}. {guild} erişiminiz moderasyon ekibinin "
            "manuel incelemesini bekliyor. Bu sekmeyi kapatabilirsiniz."
        ),
        "denied_detail": (
            "Üzgünüz, {username}. {guild} erişimi reddedildi: {reason}"
        ),
        "role_pending_detail": (
            "Teşekkürler, {username}. {guild} için doğrulamayı geçtiniz ancak "
            "bot Discord rollerinizi henüz güncelleyemedi. Erişim kısa sürede "
            "görünmezse bir sunucu yöneticisine başvurun."
        ),
        "allowed": "Tüm doğrulama kontrollerini geçtiniz.",
        "whitelisted": "Bu sunucunun beyaz listesindesiniz.",
        "user_blacklisted": "Bu sunucuda kara listedesiniz.",
        "vpn_or_proxy_detected": "VPN veya proxy bağlantısı algılandı.",
        "shared_ip_detected": "Bağlantınız başka bir doğrulanmış hesapla eşleşiyor.",
        "account_too_new": "Discord hesabınız bu sunucu için çok yeni.",
        "high_risk_guild": "Hesabınız moderasyon ekibi tarafından inceleniyor.",
    },
}


def t(lang: str, key: str) -> str:
    """Return localized public verification copy for ``key``."""

    locale = "tr" if lang == "tr" else "en"
    return COPY[locale].get(key) or COPY["en"].get(key) or key


def _t(lang: str, key: str) -> str:
    return t(lang, key)


def _identity_block(*, guild_name: str, icon_url: str | None) -> str:
    safe_name = html.escape(guild_name)
    initials = html.escape(guild_initials(guild_name))
    if icon_url:
        safe_url = html.escape(icon_url, quote=True)
        return f"""
    <div class="identity">
      <img class="icon" src="{safe_url}" width="56" height="56" alt="{safe_name}"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
      <div class="fallback" style="display:none" aria-hidden="true">{initials}</div>
    </div>"""
    return f"""
    <div class="identity">
      <div class="fallback" aria-hidden="true">{initials}</div>
    </div>"""


def _base_styles() -> str:
    return """
  body { margin: 0; min-height: 100vh; display: flex; align-items: center;
    justify-content: center; background: #09090b; color: #fafafa;
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
  .panel { max-width: 420px; padding: 40px 36px; border: 1px solid #27272a;
    border-radius: 20px; background: #101012; text-align: center; }
  .identity { width: 56px; height: 56px; margin: 0 auto 20px; }
  .icon, .fallback { width: 56px; height: 56px; border-radius: 50%;
    object-fit: cover; display: flex; align-items: center; justify-content: center; }
  .fallback { background: #3f3f46; color: #fafafa; font-weight: 700; font-size: 18px;
    border: 1px solid #52525b; }
  h1 { font-size: 22px; margin: 0 0 12px; }
  p { font-size: 15px; line-height: 1.6; color: #a1a1aa; margin: 0; }
  .actions { margin-top: 20px; }
  .actions a { display: inline-block; min-height: 40px; line-height: 40px;
    padding: 0 16px; border-radius: 10px; background: #3b82f6; color: #fff;
    text-decoration: none; font-size: 14px; font-weight: 600; }
  .brand { margin-top: 28px; font-size: 11px; letter-spacing: 0.28em;
    text-transform: uppercase; color: #52525b; }
  @media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
  }
"""


def render_verification_unavailable_page(
    *,
    guild_name: str,
    message: str,
    icon_url: str | None = None,
    lang: str = "en",
    headline: str | None = None,
    retry_href: str | None = None,
) -> str:
    """Render a neutral notice when verification cannot be started."""

    locale = "tr" if lang == "tr" else "en"
    safe_message = html.escape(message)
    title = html.escape(headline or _t(locale, "unavailable_title"))
    brand = html.escape(BRAND)
    retry = ""
    if retry_href:
        safe_href = html.escape(retry_href, quote=True)
        retry = (
            f'<div class="actions"><a href="{safe_href}">'
            f'{html.escape(_t(locale, "retry"))}</a></div>'
        )

    return f"""<!doctype html>
<html lang="{locale}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand}</title>
<style>{_base_styles()}</style>
</head>
<body>
  <div class="panel">
    {_identity_block(guild_name=guild_name, icon_url=icon_url)}
    <h1>{title}</h1>
    <p>{safe_message}</p>
    {retry}
    <div class="brand">{brand}</div>
  </div>
</body>
</html>"""


def render_verification_result_page(
    *,
    allowed: bool,
    manual_review: bool,
    reason: str,
    username: str,
    guild_name: str,
    icon_url: str | None = None,
    lang: str = "en",
    role_grant_failed: bool = False,
) -> str:
    locale = "tr" if lang == "tr" else "en"
    safe_username = html.escape(username)
    safe_guild_name = html.escape(guild_name)
    reason_text = _t(locale, reason) if reason in COPY["en"] else reason
    brand = html.escape(BRAND)

    if role_grant_failed and allowed:
        headline = _t(locale, "role_pending_title")
        accent = "#fbbf24"
        detail = _t(locale, "role_pending_detail").format(
            username=safe_username,
            guild=safe_guild_name,
        )
    elif allowed:
        headline = _t(locale, "complete_title")
        accent = "#34d399"
        detail = _t(locale, "complete_detail").format(
            username=safe_username,
            guild=safe_guild_name,
        )
    elif manual_review:
        headline = _t(locale, "pending_title")
        accent = "#fbbf24"
        detail = _t(locale, "pending_detail").format(
            username=safe_username,
            guild=safe_guild_name,
        )
    else:
        headline = _t(locale, "denied_title")
        accent = "#f87171"
        detail = _t(locale, "denied_detail").format(
            username=safe_username,
            guild=safe_guild_name,
            reason=html.escape(reason_text),
        )

    # Status accent ring around identity when no icon would otherwise show status.
    status_ring = f"box-shadow: 0 0 0 3px {accent};"

    return f"""<!doctype html>
<html lang="{locale}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand}</title>
<style>{_base_styles()}
  .identity .icon, .identity .fallback {{ {status_ring} }}
</style>
</head>
<body>
  <div class="panel">
    {_identity_block(guild_name=guild_name, icon_url=icon_url)}
    <h1>{html.escape(headline)}</h1>
    <p>{detail}</p>
    <div class="brand">{brand}</div>
  </div>
</body>
</html>"""


def message_for_setup_state(state: str, *, lang: str = "en") -> str:
    locale = "tr" if lang == "tr" else "en"
    mapping = {
        "not_configured": "not_configured",
        "incomplete": "incomplete",
        "disabled": "disabled",
        "degraded": "degraded",
        "error": "error",
        "guild_not_found": "guild_not_found",
    }
    return _t(locale, mapping.get(state, "not_configured"))
