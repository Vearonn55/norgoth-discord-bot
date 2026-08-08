"""Redis-backed shared state between the bot, the API, and the dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

BOT_HEARTBEAT_KEY = "norgoth:bot:heartbeat"
BOT_STATUS_KEY = "norgoth:bot:status"
HEARTBEAT_TTL_SECONDS = 45


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def guild_resources_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:resources"


def guild_members_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:members"


def automation_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:automation"


def modules_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:modules"


def moderation_log_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:modlog"


def welcome_status_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:welcome:status"


class BotState:
    """Publishes bot liveness, guild resources, and reads guild config."""

    def __init__(self, redis_url: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)

    async def close(self) -> None:
        await self._redis.aclose()

    async def publish_heartbeat(self) -> None:
        await self._redis.set(
            BOT_HEARTBEAT_KEY,
            now_iso(),
            ex=HEARTBEAT_TTL_SECONDS,
        )

    async def publish_status(self, status: dict[str, Any]) -> None:
        await self._redis.set(BOT_STATUS_KEY, json.dumps(status))

    async def publish_guild_resources(
        self,
        guild_id: int,
        resources: dict[str, Any],
    ) -> None:
        await self._redis.set(
            guild_resources_key(guild_id),
            json.dumps(resources),
        )

    async def publish_guild_members(
        self,
        guild_id: int,
        members: dict[str, Any],
    ) -> None:
        await self._redis.set(
            guild_members_key(guild_id),
            json.dumps(members),
        )

    async def is_module_enabled(self, guild_id: int, module: str) -> bool:
        """Modules default to enabled until explicitly turned off."""

        raw = await self._redis.get(modules_key(guild_id))

        if not raw:
            return True

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return True

        if not isinstance(parsed, dict):
            return True

        return bool(parsed.get(module, True))

    async def get_json(self, key: str) -> dict[str, Any]:
        raw = await self._redis.get(key)

        if not raw:
            return {}

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}

    async def set_json(self, key: str, value: dict[str, Any]) -> None:
        await self._redis.set(key, json.dumps(value))

    async def append_capped_list(
        self,
        key: str,
        entry: dict[str, Any],
        cap: int = 500,
    ) -> None:
        await self._redis.lpush(key, json.dumps(entry))
        await self._redis.ltrim(key, 0, cap - 1)

    @property
    def redis(self) -> redis.Redis:
        return self._redis

    async def get_automation_config(self, guild_id: int) -> dict[str, Any]:
        raw = await self._redis.get(automation_key(guild_id))

        if not raw:
            return {}

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}

    async def append_moderation_log(
        self,
        guild_id: int,
        entry: dict[str, Any],
    ) -> None:
        key = moderation_log_key(guild_id)
        await self._redis.lpush(key, json.dumps(entry))
        await self._redis.ltrim(key, 0, 499)
