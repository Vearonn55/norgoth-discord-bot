"""Redis-backed shared state between the bot, the API, and the dashboard."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as redis

BOT_HEARTBEAT_KEY = "norgoth:bot:heartbeat"
BOT_STATUS_KEY = "norgoth:bot:status"
HEARTBEAT_TTL_SECONDS = 45

logger = logging.getLogger("norgoth.bot.state")


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


def autorole_status_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:autorole:status"


class BotState:
    """Publishes bot liveness, guild resources, and reads guild config."""

    def __init__(
        self,
        redis_url: str,
        *,
        api_base_url: str | None = None,
        bot_token: str | None = None,
    ) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._api_base_url = (api_base_url or "").rstrip("/")
        self._bot_token = bot_token or ""

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

    async def _hydrate_feature_from_api(
        self,
        guild_id: int,
        feature_key: str,
    ) -> dict[str, Any]:
        """Fetch durable config from the API (Postgres) and cache into Redis."""

        if not self._api_base_url or not self._bot_token:
            return {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._api_base_url}/internal/config/{guild_id}/{feature_key}",
                    headers={"X-Norgoth-Bot-Token": self._bot_token},
                )
            if response.status_code != 200:
                logger.warning(
                    "Config hydrate for %s/%s returned HTTP %s: %s",
                    guild_id,
                    feature_key,
                    response.status_code,
                    response.text[:200],
                )
                return {}
            data = response.json()
            config = data.get("config") if isinstance(data, dict) else None
            return config if isinstance(config, dict) else {}
        except httpx.HTTPError:
            logger.exception(
                "Config hydrate failed for guild %s feature %s",
                guild_id,
                feature_key,
            )
            return {}

    async def get_automation_config(self, guild_id: int) -> dict[str, Any]:
        raw = await self._redis.get(automation_key(guild_id))

        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed

        # Redis miss (e.g. after flush): refill from Postgres via the API.
        hydrated = await self._hydrate_feature_from_api(guild_id, "automation")
        if hydrated:
            await self._redis.set(automation_key(guild_id), json.dumps(hydrated))
            logger.info(
                "Rehydrated automation config for guild %s from Postgres",
                guild_id,
            )
        return hydrated

    async def append_moderation_log(
        self,
        guild_id: int,
        entry: dict[str, Any],
    ) -> None:
        key = moderation_log_key(guild_id)
        await self._redis.lpush(key, json.dumps(entry))
        await self._redis.ltrim(key, 0, 499)
