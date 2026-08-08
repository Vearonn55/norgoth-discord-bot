"""Discord OAuth2 endpoints for the verification flow."""

import html
import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
    Request,
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
from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.integrations.discord.oauth import DiscordOAuthError
from app.integrations.discord.snowflake import (
    InvalidDiscordSnowflakeError,
    get_discord_account_age_days,
)
from app.integrations.proxycheck import (
    InvalidProxycheckIPAddressError,
    ProxycheckError,
)
from app.security.oauth_state import InvalidOAuthStateError
from app.services.verification_service import VerificationRequest

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/oauth/discord",
    tags=["discord-oauth"],
)

REASON_DESCRIPTIONS = {
    "allowed": "You passed all verification checks.",
    "whitelisted": "You are on this server's whitelist.",
    "user_blacklisted": "You are blacklisted on this server.",
    "blacklisted_guild": "You are a member of a blacklisted server.",
    "vpn_or_proxy_detected": "A VPN or proxy connection was detected.",
    "shared_ip_detected": "Your connection matches another verified account.",
    "account_too_new": "Your Discord account is too new for this server.",
}


def render_verification_result_page(
    *,
    allowed: bool,
    reason: str,
    username: str,
    guild_name: str,
) -> str:
    safe_username = html.escape(username)
    safe_guild_name = html.escape(guild_name)
    description = REASON_DESCRIPTIONS.get(reason, reason)

    if allowed:
        headline = "Verification complete"
        accent = "#34d399"
        detail = (
            f"Welcome, {safe_username}. You now have access to "
            f"{safe_guild_name}. You can close this tab and return to Discord."
        )
    else:
        headline = "Verification denied"
        accent = "#f87171"
        detail = (
            f"Sorry, {safe_username}. Access to {safe_guild_name} was denied: "
            f"{description}"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Norgoth Verification</title>
<style>
  body {{
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #09090b;
    color: #fafafa;
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  .panel {{
    max-width: 420px;
    padding: 40px 36px;
    border: 1px solid #27272a;
    border-radius: 20px;
    background: #101012;
    text-align: center;
  }}
  .dot {{
    width: 56px;
    height: 56px;
    margin: 0 auto 20px;
    border-radius: 50%;
    background: {accent};
  }}
  h1 {{ font-size: 22px; margin: 0 0 12px; }}
  p {{ font-size: 15px; line-height: 1.6; color: #a1a1aa; margin: 0; }}
  .brand {{
    margin-top: 28px;
    font-size: 11px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: #52525b;
  }}
</style>
</head>
<body>
  <div class="panel">
    <div class="dot"></div>
    <h1>{headline}</h1>
    <p>{detail}</p>
    <div class="brand">Norgoth Verification</div>
  </div>
</body>
</html>"""

DiscordGuildIDPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^\d+$",
    ),
]

AuthorizationCodeQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=2048,
    ),
]

OAuthStateQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=4096,
    ),
]


def _get_client_ip(request: Request) -> str:
    """Return the direct client IP address for verification."""

    if request.client is None or not request.client.host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The client IP address could not be determined.",
        )

    return request.client.host


@router.get(
    "/authorize/{discord_guild_id}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def authorize_discord(
    discord_guild_id: DiscordGuildIDPath,
    oauth_client: DiscordOAuthClientDependency,
    oauth_state_service: DiscordOAuthStateServiceDependency,
) -> RedirectResponse:
    """Redirect a verification attempt to Discord authorization."""

    state_value = oauth_state_service.create(
        discord_guild_id=discord_guild_id,
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
    response_class=HTMLResponse,
)
async def discord_callback(
    request: Request,
    code: AuthorizationCodeQuery,
    state_value: Annotated[
        OAuthStateQuery,
        Query(alias="state"),
    ],
    oauth_client: DiscordOAuthClientDependency,
    oauth_state_service: DiscordOAuthStateServiceDependency,
    guild_service: GuildServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    proxycheck_client: ProxycheckClientDependency,
    verification_service: VerificationServiceDependency,
    bot_client: DiscordBotClientDependency,
) -> HTMLResponse:
    """Authenticate through Discord, verify, apply roles, and show the result."""

    try:
        verified_state = oauth_state_service.verify(state_value)

        token = await oauth_client.exchange_code(
            code=code,
        )
        user = await oauth_client.get_current_user(
            access_token=token.access_token,
        )
        user_guilds = await oauth_client.get_current_user_guilds(
            access_token=token.access_token,
        )

        account_age_days = get_discord_account_age_days(user.id)
    except InvalidOAuthStateError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except InvalidDiscordSnowflakeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord returned an invalid user ID.",
        ) from error
    except DiscordOAuthError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Discord authentication could not be completed.",
        ) from error

    guild = await guild_service.get_by_discord_guild_id(verified_state.discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The Discord server is not registered.",
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)

    if configuration is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Verification is not configured for this Discord server."),
        )

    if not configuration.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Verification is currently disabled for this Discord server."),
        )

    client_ip = _get_client_ip(request)
    vpn_or_proxy_detected = False

    if configuration.deny_vpn_or_proxy:
        try:
            proxycheck_result = await proxycheck_client.check_ip(client_ip)
        except InvalidProxycheckIPAddressError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The client IP address is invalid.",
            ) from error
        except ProxycheckError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=("VPN and proxy detection could not be completed."),
            ) from error

        vpn_or_proxy_detected = proxycheck_result.vpn_or_proxy_detected

    verification_result = await verification_service.verify(
        configuration=configuration,
        request=VerificationRequest(
            guild_id=guild.id,
            discord_user_id=user.id,
            discord_user_guild_ids=frozenset(user_guild.id for user_guild in user_guilds),
            discord_account_age_days=account_age_days,
            ip_address=client_ip,
            vpn_or_proxy_detected=vpn_or_proxy_detected,
        ),
    )

    if bot_client is not None:
        if verification_result.allowed and configuration.verified_role_id:
            try:
                await bot_client.add_member_role(
                    guild_id=verified_state.discord_guild_id,
                    user_id=user.id,
                    role_id=configuration.verified_role_id,
                    reason="Norgoth verification passed",
                )

                if configuration.unverified_role_id:
                    await bot_client.remove_member_role(
                        guild_id=verified_state.discord_guild_id,
                        user_id=user.id,
                        role_id=configuration.unverified_role_id,
                        reason="Norgoth verification passed",
                    )
            except DiscordBotAPIError:
                logger.exception(
                    "Verified role grant failed for user %s in guild %s",
                    user.id,
                    verified_state.discord_guild_id,
                )
        elif not verification_result.allowed and configuration.unverified_role_id:
            try:
                await bot_client.add_member_role(
                    guild_id=verified_state.discord_guild_id,
                    user_id=user.id,
                    role_id=configuration.unverified_role_id,
                    reason=f"Norgoth verification denied: {verification_result.reason}",
                )
            except DiscordBotAPIError:
                logger.exception(
                    "Unverified role assignment failed for user %s in guild %s",
                    user.id,
                    verified_state.discord_guild_id,
                )

    return HTMLResponse(
        content=render_verification_result_page(
            allowed=verification_result.allowed,
            reason=verification_result.reason,
            username=user.global_name or user.username,
            guild_name=guild.discord_guild_name,
        ),
        status_code=status.HTTP_200_OK,
    )
