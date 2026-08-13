"""PKCE helpers for provider OAuth (Kick OAuth 2.1, TikTok, X).

Verifiers must stay server-side and never be returned to the browser after
authorization begins. Discord OAuth does not use PKCE; do not force it there.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PkcePair:
    verifier: str
    challenge: str
    method: str = "S256"


def generate_pkce(*, verifier_bytes: int = 32) -> PkcePair:
    """Create an OAuth PKCE verifier/challenge pair (S256)."""

    if verifier_bytes < 32:
        raise ValueError("PKCE verifier must be at least 32 bytes of entropy.")
    verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(verifier_bytes))
        .rstrip(b"=")
        .decode("ascii")
    )
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkcePair(verifier=verifier, challenge=challenge, method="S256")


def verify_pkce(*, verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(expected, challenge)
