"""Tests for protected IP handling in verification logs."""

from datetime import datetime, timezone
from types import SimpleNamespace
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

    guild_id = uuid4()

    def _fake_create(**kwargs: object) -> SimpleNamespace:
        # Echo the persisted attempt back to the service (which builds the view).
        return SimpleNamespace(
            id=uuid4(),
            guild_id=kwargs["guild_id"],
            status=kwargs["status"],
            reason=kwargs["reason"],
            ip_hash=kwargs["ip_hash"],
            ip_encrypted=kwargs["ip_encrypted"],
            vpn_or_proxy_detected=kwargs["vpn_or_proxy_detected"],
            shared_ip_detected=kwargs["shared_ip_detected"],
            high_risk_guild_detected=kwargs.get("high_risk_guild_detected", False),
            matched_high_risk_guild_ids=kwargs.get(
                "matched_high_risk_guild_ids"
            ),
            banned_ip_match_detected=kwargs.get("banned_ip_match_detected", False),
            matched_banned_user_ids=kwargs.get("matched_banned_user_ids"),
            review_evidence=kwargs.get("review_evidence"),
            reviewed_by=None,
            reviewed_at=None,
            created_at=datetime.now(timezone.utc),
        )

    repository = AsyncMock(spec=VerificationLogRepository)
    repository.create.side_effect = _fake_create

    ip_protection_service = _create_ip_protection_service()
    service = VerificationLogService(
        repository,
        ip_protection_service,
    )

    result = await service.create_log(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        status=VerificationStatus.SUCCESS,
        reason=None,
        ip_address=IP_ADDRESS,
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
    )

    # The returned view carries no raw/protected IP; assert on what was persisted.
    assert result.guild_id == guild_id
    assert result.discord_user_id == "123456789012345678"

    repository.create.assert_awaited_once()
    create_kwargs = repository.create.await_args.kwargs
    assert create_kwargs["ip_hash"] == ip_protection_service.hash_ip(IP_ADDRESS)
    assert create_kwargs["ip_encrypted"] != IP_ADDRESS.encode("ascii")
    assert (
        ip_protection_service.decrypt_ip(create_kwargs["ip_encrypted"]) == IP_ADDRESS
    )


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
