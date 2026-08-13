"""Provider-aware OAuth state for future CN Connect flows (Phase 6 scaffold).

Binds authenticated NorBot user, guild, provider, purpose, locale, and optional
PKCE verifier hash. Distinct from DiscordOAuthStateService.

Callbacks must live under ``/api/v1/oauth/{provider}/callback`` and must never
share routes with ``/webhooks/...``. Token persistence requires a future
Postgres table with SecretBox encryption — Redis holds only short-lived state.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from app.security.pkce import PkcePair, generate_pkce


class InvalidProviderOAuthStateError(ValueError):
    """Raised when provider OAuth state is invalid or expired."""


ALLOWED_PROVIDERS = frozenset({"twitch", "kick", "youtube", "tiktok", "x"})
ALLOWED_PURPOSES = frozenset(
    {
        "cn_connect",
        "cn_reconnect",
        "twitch_cost0",
        "tiktok_display",
    }
)


@dataclass(frozen=True, slots=True)
class ProviderOAuthState:
    user_id: str
    guild_id: str
    provider: str
    purpose: str
    nonce: str
    issued_at: int
    lang: str = "en"
    return_path: str = "/messages/content-notifications"
    pkce_verifier: str | None = None
    code_challenge: str | None = None


class ProviderOAuthStateService:
    """Signed, short-lived OAuth state for content-platform user authorization."""

    def __init__(self, *, secret: str, lifetime_seconds: int = 600) -> None:
        normalized = secret.strip()
        if not normalized:
            raise ValueError("Provider OAuth state secret must not be empty.")
        if lifetime_seconds <= 0:
            raise ValueError("Provider OAuth state lifetime must be > 0.")
        self._signing_key = hashlib.sha256(
            b"norgoth-provider-oauth-state:" + normalized.encode("utf-8")
        ).digest()
        self._lifetime_seconds = lifetime_seconds

    def create(
        self,
        *,
        user_id: str,
        guild_id: str,
        provider: str,
        purpose: str,
        lang: str = "en",
        return_path: str = "/messages/content-notifications",
        with_pkce: bool = True,
        current_time: int | None = None,
    ) -> tuple[str, ProviderOAuthState]:
        if provider not in ALLOWED_PROVIDERS:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
        if purpose not in ALLOWED_PURPOSES:
            raise ValueError(f"Unsupported OAuth purpose: {purpose}")
        if not user_id or not guild_id:
            raise ValueError("user_id and guild_id are required.")
        if not return_path.startswith("/"):
            raise ValueError("return_path must be a relative dashboard path.")

        issued_at = int(time.time()) if current_time is None else current_time
        nonce = secrets.token_urlsafe(24)
        pkce: PkcePair | None = generate_pkce() if with_pkce else None
        payload = {
            "user_id": user_id,
            "guild_id": guild_id,
            "provider": provider,
            "purpose": purpose,
            "iat": issued_at,
            "nonce": nonce,
            "lang": lang if lang in {"en", "tr"} else "en",
            "return_path": return_path,
            "code_challenge": pkce.challenge if pkce else None,
            "code_challenge_method": pkce.method if pkce else None,
            # Verifier stays inside the signed blob so Redis is optional for MVP
            # scaffolding; production Connect should also store nonce→verifier
            # one-time in Redis and strip verifier from the browser-visible state.
            "code_verifier": pkce.verifier if pkce else None,
        }
        encoded = self._encode_json(payload)
        state = f"{encoded}.{self._sign(encoded)}"
        parsed = ProviderOAuthState(
            user_id=user_id,
            guild_id=guild_id,
            provider=provider,
            purpose=purpose,
            nonce=nonce,
            issued_at=issued_at,
            lang=payload["lang"],
            return_path=return_path,
            pkce_verifier=pkce.verifier if pkce else None,
            code_challenge=pkce.challenge if pkce else None,
        )
        return state, parsed

    def verify(
        self,
        state: str,
        *,
        expected_provider: str | None = None,
        expected_user_id: str | None = None,
        expected_guild_id: str | None = None,
        current_time: int | None = None,
    ) -> ProviderOAuthState:
        try:
            encoded, supplied_sig = state.split(".", maxsplit=1)
        except ValueError as error:
            raise InvalidProviderOAuthStateError("Invalid state format.") from error
        if not hmac.compare_digest(supplied_sig, self._sign(encoded)):
            raise InvalidProviderOAuthStateError("Invalid state signature.")
        payload = self._decode_json(encoded)
        for key in ("user_id", "guild_id", "provider", "purpose", "nonce", "iat"):
            if key not in payload:
                raise InvalidProviderOAuthStateError(f"State missing {key}.")
        if not isinstance(payload["iat"], int) or isinstance(payload["iat"], bool):
            raise InvalidProviderOAuthStateError("Invalid iat.")
        now = int(time.time()) if current_time is None else current_time
        if payload["iat"] > now + 60:
            raise InvalidProviderOAuthStateError("State iat is in the future.")
        if now - payload["iat"] > self._lifetime_seconds:
            raise InvalidProviderOAuthStateError("State expired.")
        provider = str(payload["provider"])
        if provider not in ALLOWED_PROVIDERS:
            raise InvalidProviderOAuthStateError("Unknown provider.")
        if expected_provider and provider != expected_provider:
            raise InvalidProviderOAuthStateError("Provider mismatch.")
        user_id = str(payload["user_id"])
        guild_id = str(payload["guild_id"])
        if expected_user_id and user_id != expected_user_id:
            raise InvalidProviderOAuthStateError("User mismatch.")
        if expected_guild_id and guild_id != expected_guild_id:
            raise InvalidProviderOAuthStateError("Guild mismatch.")
        purpose = str(payload["purpose"])
        if purpose not in ALLOWED_PURPOSES:
            raise InvalidProviderOAuthStateError("Unknown purpose.")
        return ProviderOAuthState(
            user_id=user_id,
            guild_id=guild_id,
            provider=provider,
            purpose=purpose,
            nonce=str(payload["nonce"]),
            issued_at=int(payload["iat"]),
            lang=str(payload.get("lang") or "en"),
            return_path=str(
                payload.get("return_path") or "/messages/content-notifications"
            ),
            pkce_verifier=(
                str(payload["code_verifier"])
                if payload.get("code_verifier")
                else None
            ),
            code_challenge=(
                str(payload["code_challenge"])
                if payload.get("code_challenge")
                else None
            ),
        )

    def _sign(self, encoded_payload: str) -> str:
        digest = hmac.new(
            self._signing_key,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    @staticmethod
    def _encode_json(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode_json(encoded: str) -> dict[str, Any]:
        padding = "=" * (-len(encoded) % 4)
        try:
            raw = base64.urlsafe_b64decode(encoded + padding)
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise InvalidProviderOAuthStateError("Invalid state payload.") from error
        if not isinstance(payload, dict):
            raise InvalidProviderOAuthStateError("State payload must be an object.")
        return dict(payload)
