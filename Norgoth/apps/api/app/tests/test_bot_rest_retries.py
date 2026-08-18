"""Bounded Discord REST retries for 429 and 5xx."""

from typing import Any

import httpx
import pytest

from app.integrations.discord.bot_rest import DiscordBotClient


class SequenceClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def request(self, *args: Any, **kwargs: Any) -> httpx.Response:
        self.calls += 1
        return self.responses.pop(0)


@pytest.mark.anyio
async def test_request_retries_5xx_once(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.integrations.discord.bot_rest.asyncio.sleep",
        _no_sleep,
    )
    http_client = SequenceClient(
        [
            httpx.Response(
                500,
                json={"message": "fail"},
                request=httpx.Request("GET", "https://discord.com/api/v10/users/@me"),
            ),
            httpx.Response(
                200,
                json={"id": "1"},
                request=httpx.Request("GET", "https://discord.com/api/v10/users/@me"),
            ),
        ]
    )
    bot = DiscordBotClient("token", http_client)  # type: ignore[arg-type]
    response = await bot._request("GET", "https://discord.com/api/v10/users/@me")
    assert response.status_code == 200
    assert http_client.calls == 2


@pytest.mark.anyio
async def test_request_retries_429_with_capped_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(
        "app.integrations.discord.bot_rest.asyncio.sleep",
        _sleep,
    )
    http_client = SequenceClient(
        [
            httpx.Response(
                429,
                json={"retry_after": 9.0},
                request=httpx.Request("GET", "https://discord.com/api/v10/users/@me"),
            ),
            httpx.Response(
                200,
                json={"ok": True},
                request=httpx.Request("GET", "https://discord.com/api/v10/users/@me"),
            ),
        ]
    )
    bot = DiscordBotClient("token", http_client)  # type: ignore[arg-type]
    response = await bot._request("GET", "https://discord.com/api/v10/users/@me")
    assert response.status_code == 200
    assert slept == [5.0]
