"""Redis-backed operator dashboard sessions."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from app.services.campaign_store import get_redis

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
EXCHANGE_TTL_SECONDS = 120
COOKIE_NAME = "norgoth_session"


def session_key(session_id: str) -> str:
    return f"norgoth:session:{session_id}"


def exchange_key(code: str) -> str:
    return f"norgoth:session_exchange:{code}"


def user_token_key(user_id: str) -> str:
    """Cache OAuth access token for guild permission refreshes."""
    return f"norgoth:operator_token:{user_id}"


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
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "global_name": self.global_name,
            "avatar": self.avatar,
            "expires_at": self.expires_at,
        }


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
                ttl = max(60, int(token_expires_in or 3600))
                await redis_client.set(
                    user_token_key(user_id),
                    access_token,
                    ex=min(ttl, SESSION_TTL_SECONDS),
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
                await redis_client.delete(user_token_key(session.user_id))
        finally:
            await redis_client.aclose()

    async def get_access_token(self, user_id: str) -> str | None:
        redis_client = await get_redis()
        try:
            token = await redis_client.get(user_token_key(user_id))
            if isinstance(token, bytes):
                return token.decode("utf-8")
            return token
        finally:
            await redis_client.aclose()


__all__ = [
    "COOKIE_NAME",
    "OperatorSession",
    "SessionService",
    "SESSION_TTL_SECONDS",
]
