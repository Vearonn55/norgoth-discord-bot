"""Redis-backed operator dashboard sessions."""

from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.integrations.discord.oauth import DiscordOAuthClient, DiscordOAuthError
from app.security.secret_box import SecretBox, SecretBoxError
from app.services.campaign_store import get_redis

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
EXCHANGE_TTL_SECONDS = 120
TOKEN_REFRESH_LOCK_SECONDS = 10
COOKIE_NAME = "norgoth_session"
_ENC_PREFIX = "enc:"

logger = logging.getLogger(__name__)


def session_key(session_id: str) -> str:
    return f"norgoth:session:{session_id}"


def exchange_key(code: str) -> str:
    return f"norgoth:session_exchange:{code}"


def user_token_key(user_id: str) -> str:
    """Cache OAuth access token for guild permission refreshes."""
    return f"norgoth:operator_token:{user_id}"


def user_refresh_key(user_id: str) -> str:
    """Cache OAuth refresh token for access-token renewal."""
    return f"norgoth:operator_refresh:{user_id}"


def user_refresh_lock_key(user_id: str) -> str:
    return f"norgoth:operator_token_lock:{user_id}"


@dataclass(frozen=True, slots=True)
class OperatorSession:
    session_id: str
    user_id: str
    username: str
    global_name: str | None
    avatar: str | None
    created_at: int
    expires_at: int

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "global_name": self.global_name,
            "avatar": self.avatar,
            "expires_at": self.expires_at,
        }


def _oauth_secret_box() -> SecretBox | None:
    settings = get_settings()
    key = getattr(settings, "oauth_token_encryption_key", None)
    if key is None:
        key = getattr(settings, "webhook_encryption_key", None)
    if key is None:
        key = getattr(settings, "ip_encryption_key", None)
    if key is None:
        return None
    try:
        return SecretBox(key)
    except SecretBoxError:
        logger.warning("OAuth token encryption key is invalid; storing tokens in plaintext.")
        return None


def _seal_token(value: str) -> str:
    box = _oauth_secret_box()
    if box is None:
        logger.warning("Storing OAuth token in plaintext; encryption key is unset.")
        return value
    blob = box.encrypt(value)
    return _ENC_PREFIX + base64.b64encode(blob).decode("ascii")


def _unseal_token(raw: str) -> str | None:
    if not raw.startswith(_ENC_PREFIX):
        # Legacy plaintext tokens remain readable for one release.
        return raw
    encoded = raw[len(_ENC_PREFIX) :]
    box = _oauth_secret_box()
    if box is None:
        return None
    try:
        blob = base64.b64decode(encoded.encode("ascii"), validate=True)
        return box.decrypt(blob)
    except (SecretBoxError, ValueError):
        logger.warning("Failed to decrypt stored OAuth token; treating as missing.")
        return None


class SessionService:
    """Create and validate operator sessions stored in Redis."""

    async def create_session(
        self,
        *,
        user_id: str,
        username: str,
        global_name: str | None,
        avatar: str | None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_in: int | None = None,
    ) -> tuple[OperatorSession, str]:
        """Return (session, one-time exchange code)."""

        session_id = secrets.token_urlsafe(32)
        now = int(time.time())
        expires_at = now + SESSION_TTL_SECONDS
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "username": username,
            "global_name": global_name,
            "avatar": avatar,
            "created_at": now,
            "expires_at": expires_at,
        }

        redis_client = await get_redis()
        try:
            await redis_client.set(
                session_key(session_id),
                json.dumps(payload),
                ex=SESSION_TTL_SECONDS,
            )
            if access_token:
                await self._store_tokens(
                    redis_client,
                    user_id=user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_in=token_expires_in,
                )

            exchange_code = secrets.token_urlsafe(24)
            await redis_client.set(
                exchange_key(exchange_code),
                session_id,
                ex=EXCHANGE_TTL_SECONDS,
            )
        finally:
            await redis_client.aclose()

        session = OperatorSession(
            session_id=session_id,
            user_id=user_id,
            username=username,
            global_name=global_name,
            avatar=avatar,
            created_at=now,
            expires_at=expires_at,
        )
        return session, exchange_code

    async def exchange_code(self, code: str) -> OperatorSession | None:
        redis_client = await get_redis()
        try:
            session_id = await redis_client.get(exchange_key(code))
            if not session_id:
                return None
            await redis_client.delete(exchange_key(code))
            if isinstance(session_id, bytes):
                session_id = session_id.decode("utf-8")
            return await self.get_session(str(session_id), redis_client=redis_client)
        finally:
            await redis_client.aclose()

    async def get_session(
        self,
        session_id: str,
        *,
        redis_client: Any | None = None,
    ) -> OperatorSession | None:
        owns_client = redis_client is None
        client = redis_client or await get_redis()
        try:
            raw = await client.get(session_key(session_id))
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            if int(data.get("expires_at", 0)) < int(time.time()):
                await client.delete(session_key(session_id))
                return None
            return OperatorSession(
                session_id=str(data["session_id"]),
                user_id=str(data["user_id"]),
                username=str(data["username"]),
                global_name=data.get("global_name"),
                avatar=data.get("avatar"),
                created_at=int(data["created_at"]),
                expires_at=int(data["expires_at"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        finally:
            if owns_client:
                await client.aclose()

    async def delete_session(self, session_id: str) -> None:
        redis_client = await get_redis()
        try:
            session = await self.get_session(session_id, redis_client=redis_client)
            await redis_client.delete(session_key(session_id))
            if session:
                await self.clear_oauth_tokens(session.user_id, redis_client=redis_client)
        finally:
            await redis_client.aclose()

    async def get_access_token(self, user_id: str) -> str | None:
        redis_client = await get_redis()
        try:
            return await self._read_token(redis_client, user_token_key(user_id))
        finally:
            await redis_client.aclose()

    async def get_refresh_token(self, user_id: str) -> str | None:
        redis_client = await get_redis()
        try:
            return await self._read_token(redis_client, user_refresh_key(user_id))
        finally:
            await redis_client.aclose()

    async def clear_oauth_tokens(
        self,
        user_id: str,
        *,
        redis_client: Any | None = None,
    ) -> None:
        owns_client = redis_client is None
        client = redis_client or await get_redis()
        try:
            await client.delete(user_token_key(user_id))
            await client.delete(user_refresh_key(user_id))
            # Guild list is derived from the user token; drop it with the tokens.
            from app.api.v1.operator_discord import invalidate_operator_guilds_cache

            await invalidate_operator_guilds_cache(
                user_id,
                redis_client=client,
            )
        finally:
            if owns_client:
                await client.aclose()

    async def get_valid_access_token(
        self,
        user_id: str,
        *,
        oauth_client: DiscordOAuthClient,
        force_refresh: bool = False,
    ) -> str | None:
        """Return a usable access token, refreshing once when needed."""

        redis_client = await get_redis()
        try:
            access = None if force_refresh else await self._read_token(
                redis_client, user_token_key(user_id)
            )
            if access and not force_refresh:
                return access

            refresh = await self._read_token(redis_client, user_refresh_key(user_id))
            if not refresh:
                if access:
                    await self.clear_oauth_tokens(user_id, redis_client=redis_client)
                return None

            lock_key = user_refresh_lock_key(user_id)
            acquired = await redis_client.set(
                lock_key,
                "1",
                nx=True,
                ex=TOKEN_REFRESH_LOCK_SECONDS,
            )
            if not acquired:
                # Another request is refreshing; wait briefly then re-read.
                await _async_sleep(0.2)
                return await self._read_token(redis_client, user_token_key(user_id))

            try:
                # Re-check after lock in case another worker finished.
                if not force_refresh:
                    raced = await self._read_token(redis_client, user_token_key(user_id))
                    if raced:
                        return raced

                token = await oauth_client.refresh_access_token(refresh_token=refresh)
                await self._store_tokens(
                    redis_client,
                    user_id=user_id,
                    access_token=token.access_token,
                    refresh_token=token.refresh_token or refresh,
                    token_expires_in=token.expires_in,
                )
                return token.access_token
            except DiscordOAuthError:
                await self.clear_oauth_tokens(user_id, redis_client=redis_client)
                return None
            finally:
                await redis_client.delete(lock_key)
        finally:
            await redis_client.aclose()

    async def _store_tokens(
        self,
        redis_client: Any,
        *,
        user_id: str,
        access_token: str,
        refresh_token: str | None,
        token_expires_in: int | None,
    ) -> None:
        access_ttl = max(60, int(token_expires_in or 3600))
        await redis_client.set(
            user_token_key(user_id),
            _seal_token(access_token),
            ex=min(access_ttl, SESSION_TTL_SECONDS),
        )
        if refresh_token:
            await redis_client.set(
                user_refresh_key(user_id),
                _seal_token(refresh_token),
                ex=SESSION_TTL_SECONDS,
            )

    async def _read_token(self, redis_client: Any, key: str) -> str | None:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if not isinstance(raw, str) or not raw:
            return None
        return _unseal_token(raw)


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


__all__ = [
    "COOKIE_NAME",
    "OperatorSession",
    "SessionService",
    "SESSION_TTL_SECONDS",
]
