"""Discord REST client authenticated with the bot token.

Used by the verification callback (role grants) and the campaign worker
(channel message delivery). Gateway concerns live in apps/bot.
"""

from __future__ import annotations

import asyncio
from typing import Any, Iterable

import httpx

DISCORD_API_BASE_URL = "https://discord.com/api/v10"

# Discord channel type constants (subset we provision).
CHANNEL_TYPE_TEXT = 0
CHANNEL_TYPE_CATEGORY = 4


class DiscordBotAPIError(Exception):
    """Raised when a bot-authenticated Discord API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DiscordBotClient:
    def __init__(self, bot_token: str, http_client: httpx.AsyncClient) -> None:
        self._headers = {"Authorization": f"Bot {bot_token}"}
        self._http_client = http_client

    async def add_member_role(
        self,
        guild_id: str,
        user_id: str,
        role_id: str,
        reason: str,
    ) -> None:
        response = await self._http_client.put(
            f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
            headers={**self._headers, "X-Audit-Log-Reason": reason},
        )

        if response.status_code not in (200, 204):
            raise DiscordBotAPIError(
                f"Failed to add role: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )

    async def remove_member_role(
        self,
        guild_id: str,
        user_id: str,
        role_id: str,
        reason: str,
    ) -> None:
        response = await self._http_client.delete(
            f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
            headers={**self._headers, "X-Audit-Log-Reason": reason},
        )

        if response.status_code not in (200, 204):
            raise DiscordBotAPIError(
                f"Failed to remove role: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )

    async def send_channel_message(
        self,
        channel_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._http_client.post(
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages",
            headers=self._headers,
            json=payload,
        )

        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to send message: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    async def edit_channel_message(
        self,
        channel_id: str,
        message_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._http_client.patch(
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages/{message_id}",
            headers=self._headers,
            json=payload,
        )

        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to edit message: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    async def get_channel_message(
        self,
        channel_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Fetch a single message. Raises ``DiscordBotAPIError`` with a 404
        status code when the message no longer exists (used to detect drift)."""

        response = await self._http_client.get(
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages/{message_id}",
            headers=self._headers,
        )
        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to get message: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def list_channel_webhooks(self, channel_id: str) -> list[dict[str, Any]]:
        response = await self._http_client.get(
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}/webhooks",
            headers=self._headers,
        )
        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to list webhooks: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        data = response.json()
        return data if isinstance(data, list) else []

    async def create_channel_webhook(
        self,
        channel_id: str,
        *,
        name: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        headers = dict(self._headers)
        if reason:
            headers["X-Audit-Log-Reason"] = reason
        response = await self._http_client.post(
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}/webhooks",
            headers=headers,
            json={"name": name[:80]},
        )
        if response.status_code not in (200, 201):
            raise DiscordBotAPIError(
                f"Failed to create webhook: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def get_channel(self, channel_id: str) -> dict[str, Any]:
        response = await self._http_client.get(
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}",
            headers=self._headers,
        )
        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to get channel: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def get_guild_member(
        self,
        guild_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        response = await self._http_client.get(
            f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/members/{user_id}",
            headers=self._headers,
        )
        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to get member: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    # ── Rate-limit aware request helper ─────────────────────────────────────
    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        """Issue a request, transparently retrying on HTTP 429.

        Honours the ``retry_after`` field (or ``Retry-After`` header) that
        Discord returns, capped so a hostile value cannot stall a request for
        an unbounded amount of time.
        """

        merged = {**self._headers, **(headers or {})}

        response: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            response = await self._http_client.request(
                method, url, headers=merged, json=json
            )
            if response.status_code != 429 or attempt >= max_retries:
                return response

            retry_after = 1.0
            try:
                body = response.json()
                retry_after = float(body.get("retry_after", retry_after))
            except Exception:  # noqa: BLE001 - fall back to the header
                header_value = response.headers.get("Retry-After")
                if header_value:
                    try:
                        retry_after = float(header_value)
                    except ValueError:
                        retry_after = 1.0

            await asyncio.sleep(min(max(retry_after, 0.0), 5.0))

        assert response is not None  # loop always assigns at least once
        return response

    async def delete_channel_message(
        self,
        channel_id: str,
        message_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        headers = {"X-Audit-Log-Reason": reason} if reason else None
        response = await self._request(
            "DELETE",
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages/{message_id}",
            headers=headers,
        )
        # 404 means the message is already gone — treat as success (idempotent).
        if response.status_code not in (200, 204, 404):
            raise DiscordBotAPIError(
                f"Failed to delete message: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )

    async def get_guild(self, guild_id: str) -> dict[str, Any]:
        response = await self._request(
            "GET", f"{DISCORD_API_BASE_URL}/guilds/{guild_id}"
        )
        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to get guild: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def list_guild_channels(self, guild_id: str) -> list[dict[str, Any]]:
        response = await self._request(
            "GET", f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/channels"
        )
        if response.status_code != 200:
            raise DiscordBotAPIError(
                f"Failed to list channels: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        data = response.json()
        return data if isinstance(data, list) else []

    async def create_guild_channel(
        self,
        guild_id: str,
        *,
        name: str,
        channel_type: int = CHANNEL_TYPE_TEXT,
        parent_id: str | None = None,
        topic: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name[:100], "type": channel_type}
        if parent_id:
            payload["parent_id"] = parent_id
        if topic:
            payload["topic"] = topic[:1024]

        headers = {"X-Audit-Log-Reason": reason} if reason else None
        response = await self._request(
            "POST",
            f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/channels",
            headers=headers,
            json=payload,
        )
        if response.status_code not in (200, 201):
            raise DiscordBotAPIError(
                f"Failed to create channel: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def delete_channel(
        self,
        channel_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        headers = {"X-Audit-Log-Reason": reason} if reason else None
        response = await self._request(
            "DELETE",
            f"{DISCORD_API_BASE_URL}/channels/{channel_id}",
            headers=headers,
        )
        if response.status_code not in (200, 204, 404):
            raise DiscordBotAPIError(
                f"Failed to delete channel: HTTP {response.status_code} {response.text}",
                status_code=response.status_code,
            )


def bot_permissions_from_guild(
    guild: dict[str, Any],
    required: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Best-effort helper describing whether the bot appears able to manage
    channels for the given guild payload. Discord does not expose the bot's
    computed permissions on the guild object, so callers should treat a missing
    signal as "unknown" rather than "denied"."""

    return {
        "owner": guild.get("owner"),
        "permissions": guild.get("permissions"),
        "required": list(required or []),
    }


__all__ = [
    "CHANNEL_TYPE_TEXT",
    "CHANNEL_TYPE_CATEGORY",
    "bot_permissions_from_guild",
    "DISCORD_API_BASE_URL",
    "DiscordBotAPIError",
    "DiscordBotClient",
]
