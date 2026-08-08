"""Tests for Discord OAuth API endpoints."""

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
    ProxycheckResult,
)
from app.models.configuration import Configuration
from app.models.discord_guild import DiscordGuild
from app.security.oauth_state import (
    DiscordOAuthState,
    DiscordOAuthStateService,
    InvalidOAuthStateError,
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


def _build_test_client(
    *,
    oauth_client: AsyncMock,
    state_service: MagicMock,
    guild_service: AsyncMock,
    configuration_service: AsyncMock,
    proxycheck_client: AsyncMock,
    verification_service: AsyncMock,
) -> TestClient:
    """Create an isolated application with dependency overrides."""

    application = FastAPI()
    application.include_router(router)

    application.dependency_overrides[get_discord_oauth_client] = lambda: oauth_client
    application.dependency_overrides[get_discord_oauth_state_service] = lambda: state_service
    application.dependency_overrides[get_guild_service] = lambda: guild_service
    application.dependency_overrides[get_configuration_service] = lambda: configuration_service
    application.dependency_overrides[get_proxycheck_client] = lambda: proxycheck_client
    application.dependency_overrides[get_verification_service] = lambda: verification_service
    application.dependency_overrides[get_discord_bot_client] = lambda: None

    return TestClient(
        application,
        client=(CLIENT_IP, 50000),
    )


def _build_dependencies() -> tuple[
    AsyncMock,
    MagicMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    """Create default OAuth endpoint dependency mocks."""

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
        avatar="avatar-hash",
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
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        enabled=True,
    )

    configuration_service = AsyncMock(spec=ConfigurationService)
    configuration_service.get_by_guild_id.return_value = configuration

    proxycheck_client = AsyncMock(spec=ProxycheckClient)
    proxycheck_client.check_ip.return_value = ProxycheckResult(
        ip_address=CLIENT_IP,
        anonymous=False,
        status="ok",
    )

    verification_service = AsyncMock(spec=VerificationService)
    verification_service.verify.return_value = VerificationResult(
        allowed=True,
        reason=VerificationDecisionReason.ALLOWED,
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
    )

    return (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    )


def test_authorize_redirects_to_discord() -> None:
    """OAuth start endpoint should redirect to Discord."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    oauth_client.build_authorization_url.return_value = (
        "https://discord.com/oauth2/authorize?state=signed-state"
    )
    state_service.create.return_value = "signed-state"

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        f"/oauth/discord/authorize/{DISCORD_GUILD_ID}",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "https://discord.com/oauth2/authorize?state=signed-state"
    )

    state_service.create.assert_called_once_with(
        discord_guild_id=DISCORD_GUILD_ID,
    )
    oauth_client.build_authorization_url.assert_called_once_with(
        state="signed-state",
    )
    proxycheck_client.check_ip.assert_not_awaited()


def test_callback_completes_verification() -> None:
    """Valid callback should execute the verification workflow."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Verification complete" in response.text
    assert "Norgoth" in response.text
    assert "Verification Guild" in response.text

    oauth_client.exchange_code.assert_awaited_once_with(
        code="authorization-code",
    )
    oauth_client.get_current_user.assert_awaited_once_with(
        access_token="access-token",
    )
    oauth_client.get_current_user_guilds.assert_awaited_once_with(
        access_token="access-token",
    )
    proxycheck_client.check_ip.assert_awaited_once_with(CLIENT_IP)

    verification_service.verify.assert_awaited_once()
    verification_request = verification_service.verify.await_args.kwargs["request"]

    assert verification_request.discord_user_id == DISCORD_USER_ID
    assert verification_request.discord_user_guild_ids == frozenset({"111111111111111111"})
    assert verification_request.ip_address == CLIENT_IP
    assert verification_request.vpn_or_proxy_detected is False


def test_callback_rejects_invalid_state() -> None:
    """Invalid OAuth state should return a client error."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    state_service.verify.side_effect = InvalidOAuthStateError("Discord OAuth state is invalid.")

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "invalid-state",
        },
    )

    assert response.status_code == 400
    proxycheck_client.check_ip.assert_not_awaited()
    verification_service.verify.assert_not_awaited()


def test_callback_rejects_unregistered_guild() -> None:
    """Callback should reject an unknown verification guild."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    guild_service.get_by_discord_guild_id.return_value = None

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 404
    proxycheck_client.check_ip.assert_not_awaited()
    verification_service.verify.assert_not_awaited()


def test_callback_rejects_missing_configuration() -> None:
    """Callback should reject a guild without verification settings."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    configuration_service.get_by_guild_id.return_value = None

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 409
    proxycheck_client.check_ip.assert_not_awaited()
    verification_service.verify.assert_not_awaited()


def test_callback_rejects_disabled_configuration() -> None:
    """Callback should reject when verification is disabled."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    configuration = configuration_service.get_by_guild_id.return_value
    configuration.enabled = False

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 409
    proxycheck_client.check_ip.assert_not_awaited()
    verification_service.verify.assert_not_awaited()


def test_callback_skips_proxycheck_when_policy_is_disabled() -> None:
    """Disabled VPN protection should not query proxycheck.io."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    configuration = configuration_service.get_by_guild_id.return_value
    configuration.deny_vpn_or_proxy = False

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

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


def test_callback_returns_denied_verification_result() -> None:
    """A denied verification should still return a valid response."""

    (
        oauth_client,
        state_service,
        guild_service,
        configuration_service,
        proxycheck_client,
        verification_service,
    ) = _build_dependencies()

    verification_service.verify.return_value = VerificationResult(
        allowed=False,
        reason=VerificationDecisionReason.SHARED_IP_DETECTED,
        shared_ip_detected=True,
        blacklisted_guild_detected=False,
    )

    client = _build_test_client(
        oauth_client=oauth_client,
        state_service=state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=proxycheck_client,
        verification_service=verification_service,
    )

    response = client.get(
        "/oauth/discord/callback",
        params={
            "code": "authorization-code",
            "state": "signed-state",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Verification denied" in response.text
    assert "another verified account" in response.text

    proxycheck_client.check_ip.assert_awaited_once_with(CLIENT_IP)
