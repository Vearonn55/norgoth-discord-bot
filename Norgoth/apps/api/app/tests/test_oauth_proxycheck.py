"""Tests for proxycheck.io use in Discord OAuth verification."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_configuration_service,
    get_discord_bot_client,
    get_discord_oauth_client,
    get_discord_oauth_state_service,
    get_guild_service,
    get_proxycheck_client,
    get_verification_service,
)
from app.api.v1.oauth import router
from app.integrations.discord.oauth import (
    DiscordOAuthClient,
    DiscordOAuthGuild,
    DiscordOAuthToken,
    DiscordOAuthUser,
)
from app.integrations.proxycheck import (
    ProxycheckClient,
    ProxycheckError,
    ProxycheckResult,
)
from app.models.configuration import Configuration
from app.models.discord_guild import DiscordGuild
from app.security.oauth_state import (
    DiscordOAuthState,
    DiscordOAuthStateService,
)
from app.services.configuration_service import (
    ConfigurationService,
)
from app.services.guild_service import GuildService
from app.services.verification_decision_service import (
    VerificationDecisionReason,
)
from app.services.verification_service import (
    VerificationResult,
    VerificationService,
)

DISCORD_GUILD_ID = "123456789012345678"
DISCORD_USER_ID = "175928847299117063"
CLIENT_IP = "203.0.113.25"


def _build_client(
    *,
    deny_vpn_or_proxy: bool = True,
    vpn_or_proxy_detected: bool = False,
) -> tuple[TestClient, AsyncMock, AsyncMock]:
    """Create an OAuth application with proxycheck mocks."""

    oauth_client = AsyncMock(spec=DiscordOAuthClient)
    oauth_client.exchange_code.return_value = DiscordOAuthToken(
        access_token="access-token",
        token_type="Bearer",
        expires_in=604800,
        refresh_token="refresh-token",
        scope=frozenset({"identify", "guilds"}),
    )
    oauth_client.get_current_user.return_value = DiscordOAuthUser(
        id=DISCORD_USER_ID,
        username="norgoth",
        global_name="Norgoth",
        avatar=None,
    )
    oauth_client.get_current_user_guilds.return_value = [
        DiscordOAuthGuild(
            id="111111111111111111",
            name="Guild One",
            owner=False,
            permissions="104324673",
        )
    ]

    state_service = MagicMock(spec=DiscordOAuthStateService)
    state_service.verify.return_value = DiscordOAuthState(
        discord_guild_id=DISCORD_GUILD_ID,
        nonce="nonce",
        issued_at=1_000,
    )

    internal_guild_id = uuid4()
    guild = DiscordGuild(
        discord_guild_id=DISCORD_GUILD_ID,
        discord_guild_name="Verification Guild",
        discord_owner_id="222222222222222222",
    )
    guild.id = internal_guild_id

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    configuration = Configuration(
        guild_id=internal_guild_id,
        verification_channel_id="333333333333333333",
        log_channel_id="444444444444444444",
        verified_role_id="555555555555555555",
        unverified_role_id="666666666666666666",
        member_role_id="777777777777777777",
        minimum_account_age_days=30,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=deny_vpn_or_proxy,
        deny_shared_ip=True,
        enabled=True,
    )

    configuration_service = AsyncMock(spec=ConfigurationService)
    configuration_service.get_by_guild_id.return_value = configuration

    proxycheck_client = AsyncMock(spec=ProxycheckClient)
    proxycheck_client.check_ip.return_value = ProxycheckResult(
        ip_address=CLIENT_IP,
        anonymous=vpn_or_proxy_detected,
        status="ok",
    )

    verification_service = AsyncMock(spec=VerificationService)
    verification_service.verify.return_value = VerificationResult(
        allowed=not vpn_or_proxy_detected,
        reason=(
            VerificationDecisionReason.VPN_OR_PROXY_DETECTED
            if vpn_or_proxy_detected
            else VerificationDecisionReason.ALLOWED
        ),
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
    )

    application = FastAPI()
    application.include_router(router)

    application.dependency_overrides[get_discord_oauth_client] = lambda: oauth_client
    application.dependency_overrides[get_discord_oauth_state_service] = lambda: state_service
    application.dependency_overrides[get_guild_service] = lambda: guild_service
    application.dependency_overrides[get_configuration_service] = lambda: configuration_service
    application.dependency_overrides[get_proxycheck_client] = lambda: proxycheck_client
    application.dependency_overrides[get_verification_service] = lambda: verification_service
    application.dependency_overrides[get_discord_bot_client] = lambda: None

    return (
        TestClient(
            application,
            client=(CLIENT_IP, 50000),
        ),
        proxycheck_client,
        verification_service,
    )


def test_callback_checks_ip_when_policy_is_enabled() -> None:
    """Enabled VPN protection should query proxycheck.io."""

    client, proxycheck_client, verification_service = _build_client()

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 200

    proxycheck_client.check_ip.assert_awaited_once_with(CLIENT_IP)

    verification_request = verification_service.verify.await_args.kwargs["request"]

    assert verification_request.vpn_or_proxy_detected is False


def test_callback_passes_anonymous_detection_to_verification() -> None:
    """Anonymous IP results should reach the verification engine."""

    client, proxycheck_client, verification_service = _build_client(vpn_or_proxy_detected=True)

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 200
    assert "Verification denied" in response.text
    assert "VPN or proxy" in response.text

    proxycheck_client.check_ip.assert_awaited_once_with(CLIENT_IP)

    verification_request = verification_service.verify.await_args.kwargs["request"]

    assert verification_request.vpn_or_proxy_detected is True


def test_callback_skips_lookup_when_policy_is_disabled() -> None:
    """Disabled VPN protection should not consume API quota."""

    client, proxycheck_client, verification_service = _build_client(deny_vpn_or_proxy=False)

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 200
    proxycheck_client.check_ip.assert_not_awaited()

    verification_request = verification_service.verify.await_args.kwargs["request"]

    assert verification_request.vpn_or_proxy_detected is False


def test_callback_fails_closed_when_proxycheck_fails() -> None:
    """A failed reputation lookup should not treat the IP as clean."""

    client, proxycheck_client, verification_service = _build_client()

    proxycheck_client.check_ip.side_effect = ProxycheckError("proxycheck.io IP lookup failed.")

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 502
    verification_service.verify.assert_not_awaited()
