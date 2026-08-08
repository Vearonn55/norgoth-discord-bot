"""Tests for user-list, guild-blacklist, and verification-log services."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.blacklisted_guild import BlacklistedGuild
from app.models.enums import (
    UserListType,
    VerificationStatus,
)
from app.models.user_list_entry import UserListEntry
from app.repositories.blacklisted_guild_repository import (
    BlacklistedGuildRepository,
)
from app.repositories.user_list_repository import (
    UserListRepository,
)
from app.repositories.verification_log_repository import (
    VerificationLogRepository,
)
from app.security.ip_protection import IPProtectionService
from app.services.blacklisted_guild_service import (
    BlacklistedGuildService,
)
from app.services.user_list_service import UserListService
from app.services.verification_log_service import (
    VerificationLogService,
)

HASH_KEY = b"h" * 32
ENCRYPTION_KEY = b"e" * 32
IP_ADDRESS = "203.0.113.25"


def _create_ip_protection_service() -> IPProtectionService:
    """Create an IP protection service for verification-log tests."""

    return IPProtectionService(
        hash_key=HASH_KEY,
        encryption_key=ENCRYPTION_KEY,
    )


@pytest.mark.anyio
async def test_user_list_service_creates_missing_entry() -> None:
    """A missing user list entry should be created."""

    guild_id = uuid4()

    repository = AsyncMock(spec=UserListRepository)
    repository.get_by_guild_and_user.return_value = None
    repository.add.side_effect = lambda entry: entry

    service = UserListService(repository)

    result = await service.set_entry(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        list_type=UserListType.WHITELIST,
        reason="Trusted member",
    )

    assert result.guild_id == guild_id
    assert result.discord_user_id == "123456789012345678"
    assert result.list_type is UserListType.WHITELIST
    assert result.reason == "Trusted member"
    repository.add.assert_awaited_once_with(result)
    repository.save.assert_not_awaited()


@pytest.mark.anyio
async def test_user_list_service_updates_existing_entry() -> None:
    """An existing user list entry should be updated."""

    guild_id = uuid4()
    entry = UserListEntry(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        list_type=UserListType.BLACKLIST,
        reason="Old reason",
    )

    repository = AsyncMock(spec=UserListRepository)
    repository.get_by_guild_and_user.return_value = entry
    repository.save.side_effect = lambda saved_entry: saved_entry

    service = UserListService(repository)

    result = await service.set_entry(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        list_type=UserListType.WHITELIST,
        reason="Approved",
    )

    assert result is entry
    assert entry.list_type is UserListType.WHITELIST
    assert entry.reason == "Approved"
    repository.save.assert_awaited_once_with(entry)
    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_user_list_service_removes_existing_entry() -> None:
    """An existing user list entry should be removed."""

    guild_id = uuid4()
    entry = UserListEntry(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        list_type=UserListType.BLACKLIST,
        reason=None,
    )

    repository = AsyncMock(spec=UserListRepository)
    repository.get_by_guild_and_user.return_value = entry

    service = UserListService(repository)

    result = await service.remove_entry(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
    )

    assert result is True
    repository.delete.assert_awaited_once_with(entry)


@pytest.mark.anyio
async def test_user_list_service_returns_false_for_missing_entry() -> None:
    """Removing an unknown user list entry should report no change."""

    repository = AsyncMock(spec=UserListRepository)
    repository.get_by_guild_and_user.return_value = None

    service = UserListService(repository)

    result = await service.remove_entry(
        guild_id=uuid4(),
        discord_user_id="123456789012345678",
    )

    assert result is False
    repository.delete.assert_not_awaited()


@pytest.mark.anyio
async def test_blacklisted_guild_service_creates_missing_entry() -> None:
    """A missing blacklisted guild entry should be created."""

    guild_id = uuid4()

    repository = AsyncMock(spec=BlacklistedGuildRepository)
    repository.get_by_owner_and_target.return_value = None
    repository.add.side_effect = lambda entry: entry

    service = BlacklistedGuildService(repository)

    result = await service.set_entry(
        guild_id=guild_id,
        blacklisted_discord_guild_id="987654321098765432",
        reason="Blocked community",
    )

    assert result.guild_id == guild_id
    assert result.blacklisted_discord_guild_id == "987654321098765432"
    assert result.reason == "Blocked community"
    repository.add.assert_awaited_once_with(result)
    repository.save.assert_not_awaited()


@pytest.mark.anyio
async def test_blacklisted_guild_service_updates_existing_entry() -> None:
    """An existing blacklisted guild reason should be updated."""

    guild_id = uuid4()
    entry = BlacklistedGuild(
        guild_id=guild_id,
        blacklisted_discord_guild_id="987654321098765432",
        reason="Old reason",
    )

    repository = AsyncMock(spec=BlacklistedGuildRepository)
    repository.get_by_owner_and_target.return_value = entry
    repository.save.side_effect = lambda saved_entry: saved_entry

    service = BlacklistedGuildService(repository)

    result = await service.set_entry(
        guild_id=guild_id,
        blacklisted_discord_guild_id="987654321098765432",
        reason="Updated reason",
    )

    assert result is entry
    assert entry.reason == "Updated reason"
    repository.save.assert_awaited_once_with(entry)
    repository.add.assert_not_awaited()


@pytest.mark.anyio
async def test_blacklisted_guild_service_removes_existing_entry() -> None:
    """An existing blacklisted guild should be removed."""

    guild_id = uuid4()
    entry = BlacklistedGuild(
        guild_id=guild_id,
        blacklisted_discord_guild_id="987654321098765432",
        reason=None,
    )

    repository = AsyncMock(spec=BlacklistedGuildRepository)
    repository.get_by_owner_and_target.return_value = entry

    service = BlacklistedGuildService(repository)

    result = await service.remove_entry(
        guild_id=guild_id,
        blacklisted_discord_guild_id="987654321098765432",
    )

    assert result is True
    repository.delete.assert_awaited_once_with(entry)


@pytest.mark.anyio
async def test_verification_log_service_creates_protected_log() -> None:
    """A verification log should protect the supplied IP address."""

    guild_id = uuid4()
    repository = AsyncMock(spec=VerificationLogRepository)
    repository.add.side_effect = lambda verification_log: verification_log

    ip_protection_service = _create_ip_protection_service()
    service = VerificationLogService(
        repository,
        ip_protection_service,
    )

    result = await service.create_log(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        status=VerificationStatus.FAILED,
        reason="VPN or proxy detected",
        ip_address=IP_ADDRESS,
        vpn_or_proxy_detected=True,
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
    )

    assert result.guild_id == guild_id
    assert result.status is VerificationStatus.FAILED
    assert result.reason == "VPN or proxy detected"
    assert result.ip_hash == ip_protection_service.hash_ip(IP_ADDRESS)
    assert result.ip_encrypted != IP_ADDRESS.encode("ascii")
    assert ip_protection_service.decrypt_ip(result.ip_encrypted) == IP_ADDRESS
    assert result.vpn_or_proxy_detected is True
    repository.add.assert_awaited_once_with(result)


@pytest.mark.anyio
async def test_verification_log_service_filters_current_user() -> None:
    """Shared-IP lookup should exclude the current Discord user."""

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.list_user_ids_by_ip_hash.return_value = [
        "123456789012345678",
        "987654321098765432",
    ]

    ip_protection_service = _create_ip_protection_service()
    service = VerificationLogService(
        repository,
        ip_protection_service,
    )

    result = await service.find_other_users_with_ip(
        guild_id=uuid4(),
        discord_user_id="123456789012345678",
        ip_address=IP_ADDRESS,
    )

    assert result == ["987654321098765432"]

    repository.list_user_ids_by_ip_hash.assert_awaited_once()
    call_arguments = repository.list_user_ids_by_ip_hash.await_args.kwargs

    assert call_arguments["ip_hash"] == (ip_protection_service.hash_ip(IP_ADDRESS))


@pytest.mark.anyio
async def test_verification_log_service_detects_shared_ip() -> None:
    """A different user on the same IP should be detected."""

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.list_user_ids_by_ip_hash.return_value = [
        "987654321098765432",
    ]

    service = VerificationLogService(
        repository,
        _create_ip_protection_service(),
    )

    result = await service.has_shared_ip(
        guild_id=uuid4(),
        discord_user_id="123456789012345678",
        ip_address=IP_ADDRESS,
    )

    assert result is True


@pytest.mark.anyio
async def test_verification_log_service_ignores_same_user_ip() -> None:
    """Repeated verification by the same user should not be an alt."""

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.list_user_ids_by_ip_hash.return_value = [
        "123456789012345678",
    ]

    service = VerificationLogService(
        repository,
        _create_ip_protection_service(),
    )

    result = await service.has_shared_ip(
        guild_id=uuid4(),
        discord_user_id="123456789012345678",
        ip_address=IP_ADDRESS,
    )

    assert result is False
