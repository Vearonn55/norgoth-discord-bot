"""Tests for the complete Discord verification workflow."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.models.blacklisted_guild import BlacklistedGuild
from app.models.configuration import Configuration
from app.models.enums import (
    UserListType,
    VerificationStatus,
)
from app.models.user_list_entry import UserListEntry
from app.services.blacklisted_guild_service import (
    BlacklistedGuildService,
)
from app.services.user_list_service import UserListService
from app.services.verification_decision_service import (
    VerificationDecisionReason,
    VerificationDecisionService,
)
from app.services.verification_log_service import (
    VerificationLogService,
)
from app.services.verification_service import (
    VerificationRequest,
    VerificationService,
)

DISCORD_USER_ID = "123456789012345678"
BLACKLISTED_DISCORD_GUILD_ID = "987654321098765432"
IP_ADDRESS = "203.0.113.25"


def _build_configuration(
    *,
    guild_id: UUID,
    deny_vpn_or_proxy: bool = True,
    deny_shared_ip: bool = True,
    minimum_account_age_days: int = 30,
) -> Configuration:
    """Create a verification configuration fixture."""

    return Configuration(
        guild_id=guild_id,
        verification_channel_id="111111111111111111",
        log_channel_id="222222222222222222",
        verified_role_id="333333333333333333",
        unverified_role_id="444444444444444444",
        member_role_id="555555555555555555",
        minimum_account_age_days=minimum_account_age_days,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=deny_vpn_or_proxy,
        deny_shared_ip=deny_shared_ip,
        enabled=True,
    )


def _build_request(
    *,
    guild_id: UUID,
    user_guild_ids: frozenset[str] | None = None,
    account_age_days: int = 365,
    vpn_or_proxy_detected: bool = False,
) -> VerificationRequest:
    """Create a verification request fixture."""

    return VerificationRequest(
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        discord_user_guild_ids=(user_guild_ids if user_guild_ids is not None else frozenset()),
        discord_account_age_days=account_age_days,
        ip_address=IP_ADDRESS,
        vpn_or_proxy_detected=vpn_or_proxy_detected,
    )


def _build_service(
    *,
    user_entry: UserListEntry | None = None,
    blacklisted_guilds: list[BlacklistedGuild] | None = None,
    shared_ip_detected: bool = False,
) -> tuple[VerificationService, AsyncMock]:
    """Create a verification service with mocked dependencies."""

    user_list_service = AsyncMock(spec=UserListService)
    user_list_service.get_entry.return_value = user_entry

    blacklisted_guild_service = AsyncMock(spec=BlacklistedGuildService)
    blacklisted_guild_service.list_entries.return_value = blacklisted_guilds or []

    verification_log_service = AsyncMock(spec=VerificationLogService)
    verification_log_service.has_shared_ip.return_value = shared_ip_detected

    service = VerificationService(
        user_list_service=user_list_service,
        blacklisted_guild_service=blacklisted_guild_service,
        verification_log_service=verification_log_service,
        verification_decision_service=VerificationDecisionService(),
    )

    return service, verification_log_service


@pytest.mark.anyio
async def test_verification_allows_safe_user() -> None:
    """A user with no blocked signals should be verified."""

    guild_id = uuid4()
    service, log_service = _build_service()

    result = await service.verify(
        configuration=_build_configuration(guild_id=guild_id),
        request=_build_request(guild_id=guild_id),
    )

    assert result.allowed is True
    assert result.reason is VerificationDecisionReason.ALLOWED
    assert result.shared_ip_detected is False
    assert result.blacklisted_guild_detected is False

    log_service.create_log.assert_awaited_once_with(
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        status=VerificationStatus.SUCCESS,
        reason="allowed",
        ip_address=IP_ADDRESS,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
    )


@pytest.mark.anyio
async def test_verification_allows_whitelisted_user() -> None:
    """A whitelisted user should bypass remaining verification checks."""

    guild_id = uuid4()
    user_entry = UserListEntry(
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        list_type=UserListType.WHITELIST,
        reason="Trusted user",
    )
    blacklisted_entry = BlacklistedGuild(
        guild_id=guild_id,
        blacklisted_discord_guild_id=(BLACKLISTED_DISCORD_GUILD_ID),
        reason="Blocked server",
    )

    service, log_service = _build_service(
        user_entry=user_entry,
        blacklisted_guilds=[blacklisted_entry],
        shared_ip_detected=True,
    )

    result = await service.verify(
        configuration=_build_configuration(guild_id=guild_id),
        request=_build_request(
            guild_id=guild_id,
            user_guild_ids=frozenset({BLACKLISTED_DISCORD_GUILD_ID}),
            account_age_days=0,
            vpn_or_proxy_detected=True,
        ),
    )

    assert result.allowed is True
    assert result.reason is VerificationDecisionReason.WHITELISTED

    log_service.create_log.assert_awaited_once_with(
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        status=VerificationStatus.SUCCESS,
        reason="whitelisted",
        ip_address=IP_ADDRESS,
        vpn_or_proxy_detected=True,
        shared_ip_detected=True,
        blacklisted_guild_detected=True,
    )


@pytest.mark.anyio
async def test_verification_rejects_blacklisted_user() -> None:
    """A manually blacklisted user should be rejected."""

    guild_id = uuid4()
    user_entry = UserListEntry(
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        list_type=UserListType.BLACKLIST,
        reason="Blocked user",
    )

    service, log_service = _build_service(user_entry=user_entry)

    result = await service.verify(
        configuration=_build_configuration(guild_id=guild_id),
        request=_build_request(guild_id=guild_id),
    )

    assert result.allowed is False
    assert result.reason is VerificationDecisionReason.USER_BLACKLISTED
    assert log_service.create_log.await_args.kwargs["status"] is VerificationStatus.FAILED
    assert log_service.create_log.await_args.kwargs["reason"] == "user_blacklisted"


@pytest.mark.anyio
async def test_verification_rejects_blacklisted_guild_member() -> None:
    """Membership in a configured blocked guild should reject the user."""

    guild_id = uuid4()
    blacklisted_entry = BlacklistedGuild(
        guild_id=guild_id,
        blacklisted_discord_guild_id=(BLACKLISTED_DISCORD_GUILD_ID),
        reason="Blocked server",
    )

    service, log_service = _build_service(blacklisted_guilds=[blacklisted_entry])

    result = await service.verify(
        configuration=_build_configuration(guild_id=guild_id),
        request=_build_request(
            guild_id=guild_id,
            user_guild_ids=frozenset(
                {
                    "111111111111111111",
                    BLACKLISTED_DISCORD_GUILD_ID,
                }
            ),
        ),
    )

    assert result.allowed is False
    assert result.reason is VerificationDecisionReason.BLACKLISTED_GUILD
    assert result.blacklisted_guild_detected is True
    assert log_service.create_log.await_args.kwargs["blacklisted_guild_detected"] is True


@pytest.mark.anyio
async def test_verification_rejects_vpn_or_proxy() -> None:
    """VPN or proxy detection should reject when protection is enabled."""

    guild_id = uuid4()
    service, log_service = _build_service()

    result = await service.verify(
        configuration=_build_configuration(guild_id=guild_id),
        request=_build_request(
            guild_id=guild_id,
            vpn_or_proxy_detected=True,
        ),
    )

    assert result.allowed is False
    assert result.reason is VerificationDecisionReason.VPN_OR_PROXY_DETECTED
    assert log_service.create_log.await_args.kwargs["vpn_or_proxy_detected"] is True


@pytest.mark.anyio
async def test_verification_rejects_shared_ip() -> None:
    """An IP used by another account should reject when enabled."""

    guild_id = uuid4()
    service, log_service = _build_service(shared_ip_detected=True)

    result = await service.verify(
        configuration=_build_configuration(guild_id=guild_id),
        request=_build_request(guild_id=guild_id),
    )

    assert result.allowed is False
    assert result.reason is VerificationDecisionReason.SHARED_IP_DETECTED
    assert result.shared_ip_detected is True

    log_service.has_shared_ip.assert_awaited_once_with(
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        ip_address=IP_ADDRESS,
    )


@pytest.mark.anyio
async def test_verification_rejects_new_discord_account() -> None:
    """A Discord account below the configured age should be rejected."""

    guild_id = uuid4()
    service, log_service = _build_service()

    result = await service.verify(
        configuration=_build_configuration(
            guild_id=guild_id,
            minimum_account_age_days=30,
        ),
        request=_build_request(
            guild_id=guild_id,
            account_age_days=29,
        ),
    )

    assert result.allowed is False
    assert result.reason is VerificationDecisionReason.ACCOUNT_TOO_NEW
    assert log_service.create_log.await_args.kwargs["reason"] == "account_too_new"


@pytest.mark.anyio
async def test_disabled_vpn_policy_does_not_reject_user() -> None:
    """VPN detection should not reject when the guild disabled it."""

    guild_id = uuid4()
    service, _ = _build_service()

    result = await service.verify(
        configuration=_build_configuration(
            guild_id=guild_id,
            deny_vpn_or_proxy=False,
        ),
        request=_build_request(
            guild_id=guild_id,
            vpn_or_proxy_detected=True,
        ),
    )

    assert result.allowed is True
    assert result.reason is VerificationDecisionReason.ALLOWED


@pytest.mark.anyio
async def test_disabled_shared_ip_policy_does_not_reject_user() -> None:
    """Shared IP should not reject when the guild disabled it."""

    guild_id = uuid4()
    service, _ = _build_service(shared_ip_detected=True)

    result = await service.verify(
        configuration=_build_configuration(
            guild_id=guild_id,
            deny_shared_ip=False,
        ),
        request=_build_request(guild_id=guild_id),
    )

    assert result.allowed is True
    assert result.reason is VerificationDecisionReason.ALLOWED
