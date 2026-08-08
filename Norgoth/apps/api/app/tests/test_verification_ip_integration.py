"""Tests for protected IP handling in verification logs."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.enums import VerificationStatus
from app.repositories.verification_log_repository import (
    VerificationLogRepository,
)
from app.security.ip_protection import IPProtectionService
from app.services.verification_log_service import (
    VerificationLogService,
)

HASH_KEY = b"h" * 32
ENCRYPTION_KEY = b"e" * 32
IP_ADDRESS = "203.0.113.25"


def _create_ip_protection_service() -> IPProtectionService:
    """Create deterministic IP protection for testing."""

    return IPProtectionService(
        hash_key=HASH_KEY,
        encryption_key=ENCRYPTION_KEY,
    )


@pytest.mark.anyio
async def test_create_log_protects_ip_automatically() -> None:
    """Raw IP input should be hashed and encrypted before persistence."""

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.add.side_effect = lambda verification_log: verification_log

    ip_protection_service = _create_ip_protection_service()
    service = VerificationLogService(
        repository,
        ip_protection_service,
    )

    result = await service.create_log(
        guild_id=uuid4(),
        discord_user_id="123456789012345678",
        status=VerificationStatus.SUCCESS,
        reason=None,
        ip_address=IP_ADDRESS,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
    )

    assert result.ip_hash == ip_protection_service.hash_ip(IP_ADDRESS)
    assert result.ip_encrypted != IP_ADDRESS.encode("ascii")
    assert ip_protection_service.decrypt_ip(result.ip_encrypted) == IP_ADDRESS
    repository.add.assert_awaited_once_with(result)


@pytest.mark.anyio
async def test_shared_ip_lookup_hashes_raw_ip() -> None:
    """Shared-IP searches should use the protected deterministic hash."""

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
async def test_same_user_is_not_treated_as_shared_ip() -> None:
    """Repeated verification by one user should not be an alt match."""

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.list_user_ids_by_ip_hash.return_value = ["123456789012345678"]

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


@pytest.mark.anyio
async def test_different_user_is_treated_as_shared_ip() -> None:
    """Another user on the same IP should be detected."""

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.list_user_ids_by_ip_hash.return_value = ["987654321098765432"]

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
