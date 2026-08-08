"""Secure IP hashing, encryption, and decryption utilities."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_AES_KEY_LENGTH = 32
_AES_NONCE_LENGTH = 12
_MINIMUM_HASH_KEY_LENGTH = 32


class InvalidIPProtectionKeyError(ValueError):
    """Raised when an IP protection key is invalid."""


class InvalidEncryptedIPError(ValueError):
    """Raised when encrypted IP data cannot be authenticated or decoded."""


class IPProtectionService:
    """Protect IP addresses used during Discord verification."""

    def __init__(
        self,
        *,
        hash_key: bytes,
        encryption_key: bytes,
    ) -> None:
        """Initialize IP protection with independent secret keys."""

        if len(hash_key) < _MINIMUM_HASH_KEY_LENGTH:
            message = "IP hash key must contain at least 32 bytes."
            raise InvalidIPProtectionKeyError(message)

        if len(encryption_key) != _AES_KEY_LENGTH:
            message = "IP encryption key must contain exactly 32 bytes."
            raise InvalidIPProtectionKeyError(message)

        self._hash_key = hash_key
        self._cipher = AESGCM(encryption_key)

    def normalize(self, ip_address: str) -> str:
        """Return an IPv4 or IPv6 address in canonical form."""

        try:
            return ipaddress.ip_address(ip_address.strip()).compressed
        except ValueError as error:
            message = "Invalid IPv4 or IPv6 address."
            raise ValueError(message) from error

    def hash_ip(self, ip_address: str) -> str:
        """Return a deterministic keyed hash for alt-account matching."""

        normalized_ip = self.normalize(ip_address)

        return hmac.new(
            self._hash_key,
            normalized_ip.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    def encrypt_ip(self, ip_address: str) -> bytes:
        """Encrypt and authenticate an IP address using AES-256-GCM."""

        normalized_ip = self.normalize(ip_address)
        nonce = os.urandom(_AES_NONCE_LENGTH)
        ciphertext = self._cipher.encrypt(
            nonce,
            normalized_ip.encode("ascii"),
            None,
        )

        return nonce + ciphertext

    def decrypt_ip(self, encrypted_ip: bytes) -> str:
        """Decrypt and authenticate a previously encrypted IP address."""

        minimum_payload_length = _AES_NONCE_LENGTH + 16

        if len(encrypted_ip) < minimum_payload_length:
            message = "Encrypted IP payload is invalid."
            raise InvalidEncryptedIPError(message)

        nonce = encrypted_ip[:_AES_NONCE_LENGTH]
        ciphertext = encrypted_ip[_AES_NONCE_LENGTH:]

        try:
            plaintext = self._cipher.decrypt(
                nonce,
                ciphertext,
                None,
            )
            decoded_ip = plaintext.decode("ascii")
        except (InvalidTag, UnicodeDecodeError) as error:
            message = "Encrypted IP payload could not be authenticated."
            raise InvalidEncryptedIPError(message) from error

        try:
            return self.normalize(decoded_ip)
        except ValueError as error:
            message = "Encrypted payload does not contain a valid IP address."
            raise InvalidEncryptedIPError(message) from error
