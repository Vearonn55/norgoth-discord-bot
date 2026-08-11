"""AES-GCM secret encryption for Discord webhook tokens and similar secrets."""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_AES_KEY_LENGTH = 32
_AES_NONCE_LENGTH = 12


class SecretBoxError(ValueError):
    """Raised when secret encryption/decryption fails."""


class SecretBox:
    """Encrypt and authenticate opaque secrets with AES-256-GCM."""

    def __init__(self, encryption_key: bytes) -> None:
        if len(encryption_key) != _AES_KEY_LENGTH:
            raise SecretBoxError(
                "Webhook encryption key must contain exactly 32 bytes."
            )
        self._cipher = AESGCM(encryption_key)

    def encrypt(self, plaintext: str) -> bytes:
        nonce = os.urandom(_AES_NONCE_LENGTH)
        ciphertext = self._cipher.encrypt(
            nonce,
            plaintext.encode("utf-8"),
            None,
        )
        return nonce + ciphertext

    def decrypt(self, blob: bytes) -> str:
        if len(blob) <= _AES_NONCE_LENGTH:
            raise SecretBoxError("Encrypted secret is truncated.")
        nonce = blob[:_AES_NONCE_LENGTH]
        ciphertext = blob[_AES_NONCE_LENGTH:]
        try:
            plaintext = self._cipher.decrypt(nonce, ciphertext, None)
        except InvalidTag as error:
            raise SecretBoxError("Encrypted secret authentication failed.") from error
        return plaintext.decode("utf-8")


@lru_cache(maxsize=1)
def get_secret_box() -> SecretBox | None:
    settings = get_settings()
    key = getattr(settings, "webhook_encryption_key", None)
    if key is None:
        return None
    return SecretBox(key)


def require_secret_box() -> SecretBox:
    box = get_secret_box()
    if box is None:
        raise SecretBoxError(
            "NORGOTH_WEBHOOK_ENCRYPTION_KEY is not configured."
        )
    return box
