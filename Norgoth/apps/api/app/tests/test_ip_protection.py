"""Tests for secure verification IP handling."""

import pytest

from app.security.ip_protection import (
    InvalidEncryptedIPError,
    InvalidIPProtectionKeyError,
    IPProtectionService,
)

HASH_KEY = b"h" * 32
ENCRYPTION_KEY = b"e" * 32


def _create_service() -> IPProtectionService:
    """Create an IP protection service for testing."""

    return IPProtectionService(
        hash_key=HASH_KEY,
        encryption_key=ENCRYPTION_KEY,
    )


def test_normalize_ipv4_address() -> None:
    """IPv4 addresses should be returned in canonical form."""

    service = _create_service()

    assert service.normalize(" 203.0.113.25 ") == "203.0.113.25"


def test_normalize_ipv6_address() -> None:
    """IPv6 addresses should be compressed into canonical form."""

    service = _create_service()

    assert service.normalize("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"


@pytest.mark.parametrize(
    "invalid_ip",
    [
        "",
        "not-an-ip",
        "999.999.999.999",
        "203.0.113.25:443",
    ],
)
def test_normalize_rejects_invalid_ip(invalid_ip: str) -> None:
    """Malformed IP addresses should be rejected."""

    service = _create_service()

    with pytest.raises(
        ValueError,
        match="Invalid IPv4 or IPv6 address",
    ):
        service.normalize(invalid_ip)


def test_hash_ip_is_deterministic() -> None:
    """The same canonical IP should always produce the same hash."""

    service = _create_service()

    first_hash = service.hash_ip("203.0.113.25")
    second_hash = service.hash_ip(" 203.0.113.25 ")

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_hash_ip_differs_for_different_addresses() -> None:
    """Different IP addresses should produce different hashes."""

    service = _create_service()

    assert service.hash_ip("203.0.113.25") != service.hash_ip("203.0.113.26")


def test_hash_ip_differs_when_secret_key_changes() -> None:
    """The same IP should produce a different hash under another key."""

    first_service = _create_service()
    second_service = IPProtectionService(
        hash_key=b"x" * 32,
        encryption_key=ENCRYPTION_KEY,
    )

    assert first_service.hash_ip("203.0.113.25") != second_service.hash_ip("203.0.113.25")


def test_encrypt_and_decrypt_ipv4_address() -> None:
    """An encrypted IPv4 address should decrypt to its canonical value."""

    service = _create_service()

    encrypted_ip = service.encrypt_ip("203.0.113.25")

    assert encrypted_ip != b"203.0.113.25"
    assert service.decrypt_ip(encrypted_ip) == "203.0.113.25"


def test_encrypt_and_decrypt_ipv6_address() -> None:
    """An encrypted IPv6 address should decrypt to its canonical value."""

    service = _create_service()

    encrypted_ip = service.encrypt_ip("2001:0db8:0000:0000:0000:0000:0000:0001")

    assert service.decrypt_ip(encrypted_ip) == "2001:db8::1"


def test_repeated_encryption_uses_different_nonces() -> None:
    """Encrypting the same IP twice should produce different payloads."""

    service = _create_service()

    first_payload = service.encrypt_ip("203.0.113.25")
    second_payload = service.encrypt_ip("203.0.113.25")

    assert first_payload != second_payload
    assert service.decrypt_ip(first_payload) == "203.0.113.25"
    assert service.decrypt_ip(second_payload) == "203.0.113.25"


def test_decrypt_rejects_modified_ciphertext() -> None:
    """Modified encrypted data should fail authentication."""

    service = _create_service()
    encrypted_ip = bytearray(service.encrypt_ip("203.0.113.25"))
    encrypted_ip[-1] ^= 1

    with pytest.raises(
        InvalidEncryptedIPError,
        match="could not be authenticated",
    ):
        service.decrypt_ip(bytes(encrypted_ip))


def test_decrypt_rejects_short_payload() -> None:
    """Incomplete encrypted data should be rejected."""

    service = _create_service()

    with pytest.raises(
        InvalidEncryptedIPError,
        match="payload is invalid",
    ):
        service.decrypt_ip(b"too-short")


def test_constructor_rejects_short_hash_key() -> None:
    """The keyed hash secret should contain at least 32 bytes."""

    with pytest.raises(
        InvalidIPProtectionKeyError,
        match="at least 32 bytes",
    ):
        IPProtectionService(
            hash_key=b"short",
            encryption_key=ENCRYPTION_KEY,
        )


@pytest.mark.parametrize(
    "invalid_encryption_key",
    [
        b"",
        b"x" * 16,
        b"x" * 24,
        b"x" * 31,
        b"x" * 33,
    ],
)
def test_constructor_rejects_invalid_encryption_key(
    invalid_encryption_key: bytes,
) -> None:
    """AES-256 encryption should require exactly 32 key bytes."""

    with pytest.raises(
        InvalidIPProtectionKeyError,
        match="exactly 32 bytes",
    ):
        IPProtectionService(
            hash_key=HASH_KEY,
            encryption_key=invalid_encryption_key,
        )
