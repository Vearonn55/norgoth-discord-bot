"""Signed and time-limited Discord OAuth state handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class InvalidOAuthStateError(ValueError):
    """Raised when an OAuth state value is invalid or expired."""


@dataclass(frozen=True, slots=True)
class DiscordOAuthState:
    """Validated data stored inside a Discord OAuth state value."""

    discord_guild_id: str
    nonce: str
    issued_at: int
    purpose: str = "verification"
    lang: str = "en"


class DiscordOAuthStateService:
    """Create and verify stateless signed Discord OAuth state values."""

    def __init__(
        self,
        *,
        secret: str,
        lifetime_seconds: int = 600,
    ) -> None:
        """Initialize state signing with a Discord application secret."""

        normalized_secret = secret.strip()

        if not normalized_secret:
            message = "OAuth state secret must not be empty."
            raise ValueError(message)

        if lifetime_seconds <= 0:
            message = "OAuth state lifetime must be greater than zero."
            raise ValueError(message)

        self._signing_key = hashlib.sha256(
            b"norgoth-discord-oauth-state:" + normalized_secret.encode("utf-8")
        ).digest()
        self._lifetime_seconds = lifetime_seconds

    def create(
        self,
        *,
        discord_guild_id: str,
        current_time: int | None = None,
        purpose: str = "verification",
        lang: str = "en",
    ) -> str:
        """Create a signed OAuth state for a Discord guild."""

        if purpose != "dashboard":
            self._validate_discord_snowflake(discord_guild_id)
        elif discord_guild_id != "0":
            self._validate_discord_snowflake(discord_guild_id)

        issued_at = int(time.time()) if current_time is None else current_time

        payload = {
            "guild_id": discord_guild_id,
            "iat": issued_at,
            "nonce": secrets.token_urlsafe(24),
            "purpose": purpose,
            "lang": lang if lang in {"en", "tr"} else "en",
        }
        encoded_payload = self._encode_json(payload)
        signature = self._sign(encoded_payload)

        return f"{encoded_payload}.{signature}"

    def verify(
        self,
        state: str,
        *,
        current_time: int | None = None,
    ) -> DiscordOAuthState:
        """Verify and decode a signed Discord OAuth state."""

        try:
            encoded_payload, supplied_signature = state.split(".", maxsplit=1)
        except ValueError as error:
            message = "Discord OAuth state has an invalid format."
            raise InvalidOAuthStateError(message) from error

        expected_signature = self._sign(encoded_payload)

        if not hmac.compare_digest(
            supplied_signature,
            expected_signature,
        ):
            message = "Discord OAuth state signature is invalid."
            raise InvalidOAuthStateError(message)

        payload = self._decode_json(encoded_payload)

        guild_id = payload.get("guild_id")
        nonce = payload.get("nonce")
        issued_at = payload.get("iat")
        purpose = payload.get("purpose", "verification")
        lang = payload.get("lang", "en")

        if not isinstance(guild_id, str):
            message = "Discord OAuth state is missing a valid guild ID."
            raise InvalidOAuthStateError(message)

        if not isinstance(nonce, str) or not nonce:
            message = "Discord OAuth state is missing a valid nonce."
            raise InvalidOAuthStateError(message)

        if not isinstance(issued_at, int) or isinstance(issued_at, bool):
            message = "Discord OAuth state is missing a valid issue time."
            raise InvalidOAuthStateError(message)

        if not isinstance(purpose, str):
            purpose = "verification"
        if not isinstance(lang, str) or lang not in {"en", "tr"}:
            lang = "en"

        if purpose == "dashboard" and guild_id == "0":
            pass
        else:
            try:
                self._validate_discord_snowflake(guild_id)
            except ValueError as error:
                message = "Discord OAuth state contains an invalid guild ID."
                raise InvalidOAuthStateError(message) from error

        resolved_current_time = int(time.time()) if current_time is None else current_time

        if issued_at > resolved_current_time + 60:
            message = "Discord OAuth state issue time is invalid."
            raise InvalidOAuthStateError(message)

        if resolved_current_time - issued_at > self._lifetime_seconds:
            message = "Discord OAuth state has expired."
            raise InvalidOAuthStateError(message)

        return DiscordOAuthState(
            discord_guild_id=guild_id,
            nonce=nonce,
            issued_at=issued_at,
            purpose=purpose,
            lang=lang,
        )

    def _sign(self, encoded_payload: str) -> str:
        """Return a URL-safe HMAC signature."""

        signature = hmac.new(
            self._signing_key,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()

        return self._encode_bytes(signature)

    @classmethod
    def _encode_json(cls, payload: dict[str, object]) -> str:
        """Encode a compact JSON object for URL-safe transport."""

        serialized_payload = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        return cls._encode_bytes(serialized_payload)

    @staticmethod
    def _decode_json(encoded_payload: str) -> dict[str, Any]:
        """Decode and validate a URL-safe JSON object."""

        try:
            raw_payload = DiscordOAuthStateService._decode_bytes(encoded_payload)
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            message = "Discord OAuth state payload is invalid."
            raise InvalidOAuthStateError(message) from error

        if not isinstance(payload, dict):
            message = "Discord OAuth state payload is not an object."
            raise InvalidOAuthStateError(message)

        return dict(payload)

    @staticmethod
    def _encode_bytes(value: bytes) -> str:
        """Encode bytes without Base64 padding."""

        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode_bytes(value: str) -> bytes:
        """Decode URL-safe Base64 with restored padding."""

        padding = "=" * (-len(value) % 4)

        try:
            return base64.b64decode(
                value + padding,
                altchars=b"-_",
                validate=True,
            )
        except ValueError as error:
            message = "Discord OAuth state contains invalid Base64."
            raise InvalidOAuthStateError(message) from error

    @staticmethod
    def _validate_discord_snowflake(value: str) -> None:
        """Validate a Discord snowflake represented as a string."""

        if not value.isdigit() or not 1 <= len(value) <= 20:
            message = "Discord guild ID must contain 1 to 20 digits."
            raise ValueError(message)


__all__ = [
    "DiscordOAuthState",
    "DiscordOAuthStateService",
    "InvalidOAuthStateError",
]
