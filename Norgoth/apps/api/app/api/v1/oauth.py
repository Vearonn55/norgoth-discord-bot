"""Discord OAuth2 endpoints for the verification flow."""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.v1.dependencies import (
    ConfigurationServiceDependency,
    DiscordBotClientDependency,
    DiscordOAuthClientDependency,
    DiscordOAuthStateServiceDependency,
    GuildServiceDependency,
    ProxycheckClientDependency,
    VerificationServiceDependency,
)
from app.core.config import get_settings
from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.integrations.discord.oauth import DiscordOAuthError
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
from app.services.verification_html import (
    message_for_setup_state,
    render_verification_unavailable_page,
)
from app.services.verification_service import VerificationRequest
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


def _html_unavailable(
    *,
    guild_name: str,
    icon_url: str | None,
    state: str,
    lang: str,
    retry_href: str | None = None,
    message: str | None = None,
) -> HTMLResponse:
    content = render_verification_unavailable_page(
        guild_name=guild_name,
        message=message or message_for_setup_state(state, lang=lang),
        icon_url=icon_url,
        lang=lang,
        retry_href=retry_href,
    )
    return HTMLResponse(content=content, status_code=status.HTTP_200_OK)


def _verify_result_redirect(
    request: Request,
    *,
    lang: str,
    outcome: str,
    reason: str,
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
        }
    )
    return RedirectResponse(
        url=f"{base}/{locale}/verify/result?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
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
) -> Response:
    """Redirect a verification attempt to Discord authorization when active."""

    lang = _request_lang(request)
    retry_href = str(request.url)

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
        return _html_unavailable(
            guild_name="this server",
            icon_url=None,
            state="error",
            lang=lang,
            retry_href=retry_href,
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
        return _html_unavailable(
            guild_name=meta.name,
            icon_url=meta.icon_url,
            state="guild_not_found",
            lang=lang,
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)
    setup = derive_verification_setup_state(configuration)

    if setup.state != "active":
        logger.info(
            "verification_authorize code=%s state=%s guild_id=%s",
            setup.code,
            setup.state,
            discord_guild_id,
        )
        retry = retry_href if setup.state in {"degraded", "error"} else None
        return _html_unavailable(
            guild_name=meta.name,
            icon_url=meta.icon_url,
            state=setup.state,
            lang=lang,
            retry_href=retry,
        )

    state_value = oauth_state_service.create(
        discord_guild_id=discord_guild_id,
        lang=lang,
    )
    authorization_url = oauth_client.build_authorization_url(
        state=state_value,
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
        _log_callback_event(request, stage="oauth_callback", code="oauth_invalid")
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
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
        user_guilds = await oauth_client.get_current_user_guilds(
            access_token=token.access_token,
        )
        account_age_days = get_discord_account_age_days(user.id)
    except InvalidDiscordSnowflakeError:
        _log_callback_event(
            request,
            stage="guild_membership",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
        )
    except DiscordOAuthError as oauth_error:
        logger.info(
            "verification_callback code=oauth_guilds_failed operation=%s status=%s",
            oauth_error.operation,
            oauth_error.http_status,
        )
        _log_callback_event(
            request,
            stage="guild_membership",
            code=_reason_from_oauth_error(oauth_error),
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request,
            lang=lang,
            outcome="error",
            reason=_reason_from_oauth_error(oauth_error),
        )

    guild = await guild_service.get_by_discord_guild_id(verified_state.discord_guild_id)
    meta = await resolve_guild_public_meta(
        discord_guild_id=verified_state.discord_guild_id,
        fallback_name=guild.discord_guild_name if guild is not None else "this server",
        bot_client=bot_client,
    )

    if guild is None:
        _log_callback_event(
            request,
            stage="guild_lookup",
            code="oauth_invalid",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="oauth_invalid"
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
            request, lang=lang, outcome="error", reason="verification_not_configured"
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
            request, lang=lang, outcome="error", reason=reason_code
        )

    user_guild_ids = frozenset(user_guild.id for user_guild in user_guilds)
    if verified_state.discord_guild_id not in user_guild_ids:
        logger.info(
            "verification_callback code=user_not_in_guild user_id=%s guild_id=%s",
            user.id,
            verified_state.discord_guild_id,
        )
        _log_callback_event(
            request,
            stage="guild_membership",
            code="not_in_guild",
            guild_id=verified_state.discord_guild_id,
        )
        return _verify_result_redirect(
            request, lang=lang, outcome="error", reason="not_in_guild"
        )

    if bot_client is not None:
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
                    request, lang=lang, outcome="error", reason="not_in_guild"
                )
            logger.info(
                "verification_callback code=guild_metadata_unavailable status=%s",
                membership_error.status_code,
            )

    vpn_or_proxy_detected = False
    if configuration.deny_vpn_or_proxy:
        try:
            proxycheck_result = await proxycheck_client.check_ip(client_ip)
            vpn_or_proxy_detected = proxycheck_result.vpn_or_proxy_detected
        except InvalidProxycheckIPAddressError:
            _log_callback_event(
                request,
                stage="risk_provider",
                code="risk_provider_unavailable",
                guild_id=verified_state.discord_guild_id,
            )
            return _verify_result_redirect(
                request, lang=lang, outcome="error", reason="risk_provider_unavailable"
            )
        except ProxycheckError:
            _log_callback_event(
                request,
                stage="risk_provider",
                code="risk_provider_unavailable",
                guild_id=verified_state.discord_guild_id,
            )
            return _verify_result_redirect(
                request, lang=lang, outcome="error", reason="risk_provider_unavailable"
            )

    try:
        verification_result = await verification_service.verify(
            configuration=configuration,
            request=VerificationRequest(
                guild_id=guild.id,
                discord_user_id=user.id,
                discord_user_guild_ids=user_guild_ids,
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
            request, lang=lang, outcome="error", reason="verification_processing_failed"
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
        request, lang=lang, outcome=outcome, reason=reason
    )


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
