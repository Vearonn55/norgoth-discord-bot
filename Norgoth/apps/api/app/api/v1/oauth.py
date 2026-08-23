"""Discord OAuth2 endpoints for the verification flow."""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import urlencode
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse

from app.api.v1.dependencies import (
    ConfigurationServiceDependency,
    DiscordBotClientDependency,
    DiscordOAuthClientDependency,
    DiscordOAuthStateServiceDependency,
    GuildServiceDependency,
    HighRiskGuildServiceDependency,
    ProxycheckClientDependency,
    VerificationServiceDependency,
)
from app.core.config import get_settings
from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.integrations.discord.oauth import (
    DiscordOAuthError,
    VERIFICATION_OAUTH_SCOPES,
)
from app.integrations.discord.snowflake import (
    InvalidDiscordSnowflakeError,
    get_discord_account_age_days,
)
from app.services.logging_presentation import (
    apply_log_title_emoji,
    filter_log_embed_fields,
)
from app.services.verification_log_routing import (
    classification_to_event_type,
    resolve_verification_log_channel,
)
from app.integrations.proxycheck import (
    InvalidProxycheckIPAddressError,
    ProxycheckError,
)
from app.security.oauth_nonce import OAuthNonceReplayError, consume_oauth_nonce
from app.security.oauth_state import InvalidOAuthStateError
from app.security.client_ip import get_trusted_client_ip
from app.security.verification_rate_limit import (
    AUTHORIZE_LIMIT,
    AUTHORIZE_WINDOW_SECONDS,
    CALLBACK_LIMIT,
    CALLBACK_WINDOW_SECONDS,
    VerificationRateLimitExceeded,
    enforce_verification_rate_limit,
)
from app.services.guild_meta import resolve_guild_public_meta
from app.services.verification_service import VerificationRequest
from app.services.verification_guild_membership import resolve_matched_high_risk_guilds
from app.services.verification_setup import derive_verification_setup_state
from app.services.views import ConfigurationView

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/oauth/discord",
    tags=["discord-oauth"],
)

DiscordGuildIDPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^\d+$",
    ),
]


def _request_lang(request: Request, fallback: str = "en") -> str:
    query_lang = request.query_params.get("lang")
    if query_lang in {"en", "tr"}:
        return query_lang
    return fallback if fallback in {"en", "tr"} else "en"


def _get_client_ip(request: Request) -> str:
    """Return the real client IP, preferring trusted proxy headers."""

    return get_trusted_client_ip(request)


def _verify_result_redirect(
    request: Request,
    *,
    lang: str,
    outcome: str,
    reason: str,
    display_context: str | None = None,
) -> RedirectResponse:
    """303 to the dashboard public result page (never include code/state)."""

    cid = str(getattr(request.state, "request_id", "") or "")
    base = (get_settings().dashboard_public_url or "https://www.norbot.io").rstrip(
        "/"
    )
    locale = lang if lang in {"en", "tr"} else "en"
    query = urlencode(
        {
            "outcome": outcome,
            "reason": reason,
            "cid": cid,
            **({"ctx": display_context} if display_context else {}),
        }
    )
    return RedirectResponse(
        url=f"{base}/{locale}/verify/result?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _safe_discord_icon_url(candidate: str | None) -> str | None:
    """Allow only trusted Discord CDN URLs for public guild identity images."""

    if not candidate:
        return None
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme != "https":
        return None
    if parsed.netloc.lower() != "cdn.discordapp.com":
        return None
    if not parsed.path.startswith("/icons/"):
        return None
    return candidate


def _build_public_verify_url(
    *,
    lang: str,
    state: str,
    display_context: str | None = None,
    retry: bool = False,
) -> str:
    base = (get_settings().dashboard_public_url or "https://www.norbot.io").rstrip("/")
    locale = lang if lang in {"en", "tr"} else "en"
    query: dict[str, str] = {"state": state}
    if display_context:
        query["ctx"] = display_context
    if retry:
        query["retry"] = "1"
    return f"{base}/{locale}/verify?{urlencode(query)}"


def _build_display_context_token(
    *,
    oauth_state_service: DiscordOAuthStateServiceDependency,
    guild_id: str,
    guild_name: str,
    guild_icon_url: str | None,
    lang: str,
) -> str:
    return oauth_state_service.create_display_context(
        guild_id=guild_id,
        guild_name=guild_name,
        guild_icon_url=_safe_discord_icon_url(guild_icon_url),
        lang=lang,
    )


def _reason_from_oauth_error(error: DiscordOAuthError) -> str:
    if error.http_status == 429:
        return "discord_rate_limited"
    if error.operation == "token_exchange" and error.http_status == 400:
        return "oauth_expired"
    if error.operation == "token_exchange":
        return "oauth_invalid"
    return "discord_unavailable"


def _log_callback_event(
    request: Request,
    *,
    stage: str,
    code: str,
    guild_id: str | None = None,
    outcome: str = "error",
) -> None:
    request_id = str(getattr(request.state, "request_id", "") or "")
    logger.info(
        "verification_callback request_id=%s stage=%s code=%s guild_id=%s outcome=%s",
        request_id,
        stage,
        code,
        guild_id or "",
        outcome,
    )


async def _proxycheck_vpn_or_proxy_detected(
    *,
    request: Request,
    configuration: ConfigurationView,
    proxycheck_client: ProxycheckClientDependency,
    client_ip: str,
    guild_id: str,
) -> bool:
    """Return the VPN/proxy signal, degrading open if the provider is unavailable."""

    if not configuration.deny_vpn_or_proxy:
        return False

    try:
        proxycheck_result = await proxycheck_client.check_ip(client_ip)
    except (InvalidProxycheckIPAddressError, ProxycheckError):
        logger.warning(
            "verification_callback code=risk_provider_unavailable_skipped guild_id=%s",
            guild_id,
            exc_info=True,
        )
        _log_callback_event(
            request,
            stage="risk_provider",
            code="risk_provider_unavailable_skipped",
            guild_id=guild_id,
            outcome="continued",
        )
        return False

    return proxycheck_result.vpn_or_proxy_detected


@router.get(
    "/authorize/{discord_guild_id}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def authorize_discord(
    request: Request,
    discord_guild_id: DiscordGuildIDPath,
    oauth_client: DiscordOAuthClientDependency,
    oauth_state_service: DiscordOAuthStateServiceDependency,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    bot_client: DiscordBotClientDependency,
    start: Annotated[bool, Query()] = False,
) -> Response:
    """Redirect a verification attempt to Discord authorization when active."""

    lang = _request_lang(request)

    try:
        client_ip = _get_client_ip(request)
        await enforce_verification_rate_limit(
            bucket="authorize",
            identity=f"{client_ip}:{discord_guild_id}",
            limit=AUTHORIZE_LIMIT,
            window_seconds=AUTHORIZE_WINDOW_SECONDS,
        )
    except VerificationRateLimitExceeded:
        logger.warning(
            "verification_authorize_rate_limited guild_id=%s",
            discord_guild_id,
        )
        return RedirectResponse(
            url=_build_public_verify_url(lang=lang, state="error", retry=True),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception:
        logger.info("authorize rate-limit check skipped", exc_info=True)

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)
    fallback_name = guild.discord_guild_name if guild is not None else "this server"
    meta = await resolve_guild_public_meta(
        discord_guild_id=discord_guild_id,
        fallback_name=fallback_name,
        bot_client=bot_client,
    )

    if guild is None:
        logger.info(
            "verification_authorize code=guild_not_found guild_id=%s",
            discord_guild_id,
        )
        context_token = _build_display_context_token(
            oauth_state_service=oauth_state_service,
            guild_id=discord_guild_id,
            guild_name=meta.name,
            guild_icon_url=meta.icon_url,
            lang=lang,
        )
        return RedirectResponse(
            url=_build_public_verify_url(
                lang=lang,
                state="guild_not_found",
                display_context=context_token,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)
    setup = derive_verification_setup_state(configuration)
    context_token = _build_display_context_token(
        oauth_state_service=oauth_state_service,
        guild_id=discord_guild_id,
        guild_name=meta.name,
        guild_icon_url=meta.icon_url,
        lang=lang,
    )

    if setup.state != "active":
        logger.info(
            "verification_authorize code=%s state=%s guild_id=%s",
            setup.code,
            setup.state,
            discord_guild_id,
        )
        return RedirectResponse(
            url=_build_public_verify_url(
                lang=lang,
                state=setup.state,
                display_context=context_token,
                retry=setup.state in {"degraded", "error"},
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not start:
        return RedirectResponse(
            url=_build_public_verify_url(
                lang=lang,
                state="ready",
                display_context=context_token,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    state_value = oauth_state_service.create(
        discord_guild_id=discord_guild_id,
        lang=lang,
    )
    authorization_url = oauth_client.build_authorization_url(
        state=state_value,
        scopes=VERIFICATION_OAUTH_SCOPES,
        prompt=None,
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get(
    "/callback",
)
async def discord_callback(
    request: Request,
    oauth_client: DiscordOAuthClientDependency,
    oauth_state_service: DiscordOAuthStateServiceDependency,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    proxycheck_client: ProxycheckClientDependency,
    verification_service: VerificationServiceDependency,
    high_risk_guild_service: HighRiskGuildServiceDependency,
    bot_client: DiscordBotClientDependency,
    code: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
    state_value: Annotated[
        str | None,
        Query(alias="state", min_length=1, max_length=4096),
    ] = None,
    error: Annotated[str | None, Query()] = None,
) -> Response:
    """Authenticate through Discord, verify, apply roles, and redirect to the dashboard."""

    lang = _request_lang(request)

    if error:
        reason = "oauth_denied" if error == "access_denied" else "oauth_invalid"
        _log_callback_event(request, stage="oauth_callback", code=reason)
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason=reason
        )

    if not code or not state_value:
        _log_callback_event(request, stage="oauth_callback", code="oauth_invalid")
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )

    try:
        client_ip = _get_client_ip(request)
    except ValueError:
        _log_callback_event(request, stage="client_ip", code="client_ip_unavailable")
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="client_ip_unavailable"
        )

    try:
        await enforce_verification_rate_limit(
            bucket="callback",
            identity=client_ip,
            limit=CALLBACK_LIMIT,
            window_seconds=CALLBACK_WINDOW_SECONDS,
        )
    except VerificationRateLimitExceeded:
        _log_callback_event(request, stage="callback_rate_limit", code="discord_rate_limited")
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="discord_rate_limited"
        )
    except Exception:
        logger.info("callback rate-limit check skipped", exc_info=True)

    try:
        verified_state = oauth_state_service.verify(state_value)
    except InvalidOAuthStateError:
        _log_callback_event(request, stage="state_verify", code="oauth_invalid")
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )

    if verified_state.purpose != "verification":
        _log_callback_event(
            request,
            stage="state_verify",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )

    lang = verified_state.lang if verified_state.lang in {"en", "tr"} else lang

    try:
        await consume_oauth_nonce(verified_state.nonce)
    except OAuthNonceReplayError:
        _log_callback_event(
            request,
            stage="nonce_consume",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )
    except Exception:
        logger.exception("verification_callback code=oauth_state_invalid nonce_backend")
        _log_callback_event(
            request,
            stage="nonce_consume",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )

    try:
        token = await oauth_client.exchange_code(code=code)
    except DiscordOAuthError as oauth_error:
        logger.info(
            "verification_callback code=oauth_token_failed operation=%s status=%s",
            oauth_error.operation,
            oauth_error.http_status,
        )
        _log_callback_event(
            request,
            stage="token_exchange",
            code=_reason_from_oauth_error(oauth_error),
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason=_reason_from_oauth_error(oauth_error),
        )

    try:
        user = await oauth_client.get_current_user(access_token=token.access_token)
    except DiscordOAuthError as oauth_error:
        logger.info(
            "verification_callback code=oauth_user_failed operation=%s status=%s",
            oauth_error.operation,
            oauth_error.http_status,
        )
        _log_callback_event(
            request,
            stage="current_user",
            code=_reason_from_oauth_error(oauth_error),
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason=_reason_from_oauth_error(oauth_error),
        )

    try:
        account_age_days = get_discord_account_age_days(user.id)
    except InvalidDiscordSnowflakeError:
        _log_callback_event(
            request,
            stage="account_age",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )

    guild = await guild_service.get_by_discord_guild_id(verified_state.discord_guild_id)
    meta = await resolve_guild_public_meta(
        discord_guild_id=verified_state.discord_guild_id,
        fallback_name=guild.discord_guild_name if guild is not None else "this server",
        bot_client=bot_client,
    )
    context_token = _build_display_context_token(
        oauth_state_service=oauth_state_service,
        guild_id=verified_state.discord_guild_id,
        guild_name=meta.name,
        guild_icon_url=meta.icon_url,
        lang=lang,
    )

    if guild is None:
        _log_callback_event(
            request,
            stage="guild_lookup",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason="oauth_invalid",
            display_context=context_token,
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)
    setup = derive_verification_setup_state(configuration)
    if configuration is None:
        _log_callback_event(
            request,
            stage="config_lookup",
            code="verification_not_configured",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason="verification_not_configured",
            display_context=context_token,
        )
    if setup.state != "active":
        reason_code = setup.code if setup.code else "verification_unavailable"
        _log_callback_event(
            request,
            stage="config_lookup",
            code=reason_code,
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason=reason_code,
            display_context=context_token,
        )

    if bot_client is None:
        _log_callback_event(
            request,
            stage="bot_membership_check",
            code="verification_unavailable",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason="verification_unavailable",
            display_context=context_token,
        )

    try:
        await bot_client.get_guild_member(
            verified_state.discord_guild_id,
            user.id,
        )
    except DiscordBotAPIError as membership_error:
        if membership_error.status_code == 404:
            _log_callback_event(
                request,
                stage="bot_membership_check",
                code="not_in_guild",
                guild_id=verified_state.discord_guild_id,
            )
            return _verify_result_redirect(
                request,
                lang=lang,
                outcome="error",
                reason="not_in_guild",
                display_context=context_token,
            )
        logger.info(
            "verification_callback code=guild_metadata_unavailable status=%s",
            membership_error.status_code,
        )
        _log_callback_event(
            request,
            stage="bot_membership_check",
            code="verification_unavailable",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason="verification_unavailable",
            display_context=context_token,
        )

    high_risk_guild_entries = await high_risk_guild_service.list_entries(guild.id)
    high_risk_guild_ids = frozenset(
        entry.high_risk_discord_guild_id for entry in high_risk_guild_entries
    )
    matched_high_risk_guild_ids = await resolve_matched_high_risk_guilds(
        bot_client,
        user_id=user.id,
        high_risk_guild_ids=high_risk_guild_ids,
    )

    vpn_or_proxy_detected = await _proxycheck_vpn_or_proxy_detected(
        request=request,
        configuration=configuration,
        proxycheck_client=proxycheck_client,
        client_ip=client_ip,
        guild_id=verified_state.discord_guild_id,
    )

    try:
        verification_result = await verification_service.verify(
            configuration=configuration,
            request=VerificationRequest(
                guild_id=guild.id,
                discord_user_id=user.id,
                matched_high_risk_guild_ids=matched_high_risk_guild_ids,
                discord_account_age_days=account_age_days,
                ip_address=client_ip,
                vpn_or_proxy_detected=vpn_or_proxy_detected,
            ),
        )
    except Exception:
        logger.exception("verification_callback code=verification_processing_failed")
        _log_callback_event(
            request,
            stage="verification_decision",
            code="verification_processing_failed",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason="verification_processing_failed",
            display_context=context_token,
        )

    role_grant_failed = False
    username = user.global_name or user.username

    if bot_client is not None:
        role_grant_failed = await _apply_verification_roles(
            bot_client=bot_client,
            discord_guild_id=verified_state.discord_guild_id,
            user_id=user.id,
            configuration=configuration,
            allowed=verification_result.allowed,
            reason=verification_result.reason,
        )

        await _send_verification_log_embed(
            bot_client=bot_client,
            discord_guild_id=verified_state.discord_guild_id,
            legacy_log_channel_id=configuration.log_channel_id,
            user_id=user.id,
            username=username,
            allowed=verification_result.allowed,
            manual_review=verification_result.manual_review,
            reason=verification_result.reason,
            role_grant_failed=role_grant_failed,
            review_role_id=configuration.manual_review_role_id,
            vpn_or_proxy_detected=vpn_or_proxy_detected,
            shared_ip_detected=verification_result.shared_ip_detected,
            high_risk_guild_detected=verification_result.high_risk_guild_detected,
        )

    if verification_result.manual_review:
        outcome = "pending"
    elif verification_result.allowed:
        outcome = "granted"
    else:
        outcome = "denied"
    reason = str(verification_result.reason)
    if role_grant_failed and verification_result.allowed:
        outcome = "error"
        reason = "role_grant_failed"
    _log_callback_event(
        request,
        stage="finalize",
        code=reason,
        guild_id=verified_state.discord_guild_id,
        outcome=outcome,
    )

    return _verify_result_redirect(
        request,
        lang=lang,
        outcome=outcome,
        reason=reason,
        display_context=context_token,
    )


@router.get("/display-context")
async def get_display_context(
    token: Annotated[str, Query(alias="ctx", min_length=8, max_length=4096)],
    oauth_state_service: DiscordOAuthStateServiceDependency,
) -> dict[str, str | None]:
    """Resolve signed public display context for verification pages."""

    context = oauth_state_service.verify_display_context(token)
    return {
        "guild_id": context.guild_id,
        "guild_name": context.guild_name,
        "guild_icon_url": context.guild_icon_url,
        "lang": context.lang,
    }


async def _apply_verification_roles(
    *,
    bot_client: DiscordBotClient,
    discord_guild_id: str,
    user_id: str,
    configuration: ConfigurationView,
    allowed: bool,
    reason: str,
) -> bool:
    """Apply role transitions. Returns True when an allowed grant failed."""

    already_verified = False
    try:
        member = await bot_client.get_guild_member(discord_guild_id, user_id)
        member_roles = {str(role_id) for role_id in (member.get("roles") or [])}
        if (
            configuration.member_role_id
            and configuration.member_role_id in member_roles
            and (
                not configuration.unverified_role_id
                or configuration.unverified_role_id not in member_roles
            )
        ):
            already_verified = True
    except DiscordBotAPIError:
        member_roles = set()

    if allowed and configuration.member_role_id:
        if already_verified:
            return False
        try:
            await bot_client.add_member_role(
                guild_id=discord_guild_id,
                user_id=user_id,
                role_id=configuration.member_role_id,
                reason="NorBot verification passed",
            )
            if configuration.unverified_role_id:
                await bot_client.remove_member_role(
                    guild_id=discord_guild_id,
                    user_id=user_id,
                    role_id=configuration.unverified_role_id,
                    reason="NorBot verification passed",
                )
            return False
        except DiscordBotAPIError:
            logger.exception(
                "verification_callback code=role_assignment_failed user_id=%s guild_id=%s",
                user_id,
                discord_guild_id,
            )
            return True

    if not allowed and configuration.unverified_role_id:
        try:
            await bot_client.add_member_role(
                guild_id=discord_guild_id,
                user_id=user_id,
                role_id=configuration.unverified_role_id,
                reason=f"NorBot verification held: {reason}",
            )
        except DiscordBotAPIError:
            logger.exception(
                "Unverified role assignment failed for user %s in guild %s",
                user_id,
                discord_guild_id,
            )
    return False


async def _send_verification_log_embed(
    *,
    bot_client: DiscordBotClient,
    discord_guild_id: str,
    legacy_log_channel_id: str,
    user_id: str,
    username: str,
    allowed: bool,
    manual_review: bool,
    reason: str,
    role_grant_failed: bool,
    review_role_id: str,
    vpn_or_proxy_detected: bool,
    shared_ip_detected: bool,
    high_risk_guild_detected: bool,
) -> None:
    event_type = classification_to_event_type(
        allowed=allowed,
        manual_review=manual_review,
        role_grant_failed=role_grant_failed,
    )
    log_channel_id, source = await resolve_verification_log_channel(
        discord_guild_id=discord_guild_id,
        event_type=event_type,
        legacy_log_channel_id=legacy_log_channel_id,
    )
    if not log_channel_id:
        return

    if allowed and not role_grant_failed:
        title = "Verification succeeded"
        color = 0x34D399
        state = "Allowed"
    elif allowed and role_grant_failed:
        title = "Verification succeeded — role pending"
        color = 0xFBBF24
        state = "Role pending"
    elif manual_review:
        title = "Manual Review Required"
        color = 0xFBBF24
        state = "Manual Review"
    else:
        title = "Verification denied"
        color = 0xF87171
        state = "Denied"

    title = apply_log_title_emoji(event_type, title)

    reasons: list[str] = []
    if vpn_or_proxy_detected:
        reasons.append("VPN / Proxy detected")
    if shared_ip_detected:
        reasons.append("Shared IP / possible alternate account")
    if high_risk_guild_detected:
        reasons.append("Member of a configured High Risk Server")
    if reason and reason not in {"allowed", "whitelisted"}:
        reasons.append(reason.replace("_", " "))

    trigger = "; ".join(reasons) if reasons else "Policy decision"

    content = None
    allowed_roles: list[str] = []
    if manual_review and review_role_id:
        content = f"<@&{review_role_id}>"
        allowed_roles = [review_role_id]

    embed = {
        "title": title,
        "color": color,
        "fields": filter_log_embed_fields(
            [
                {
                    "name": "User",
                    "value": f"<@{user_id}> (`{user_id}`)",
                    "inline": False,
                },
                {"name": "Display", "value": username[:80] or "—", "inline": True},
                {"name": "State", "value": state, "inline": True},
                {"name": "Trigger", "value": trigger[:256], "inline": False},
            ]
        ),
    }

    payload: dict[str, object] = {
        "embeds": [embed],
        "allowed_mentions": {"parse": [], "roles": allowed_roles},
    }
    if content:
        payload["content"] = content

    try:
        await bot_client.send_channel_message(log_channel_id, payload)
    except DiscordBotAPIError:
        logger.exception(
            "verification_log_embed_failed user_id=%s guild_id=%s "
            "channel_id=%s source=%s event_type=%s",
            user_id,
            discord_guild_id,
            log_channel_id,
            source,
            event_type,
        )
