"""HTTP status mapping, multi-id persist, and deploy idempotency helpers."""

from types import SimpleNamespace
from typing import Any

import pytest
from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.routes.embed_messages import (
    OWNER_LIBRARY,
    _apply_sent_ids,
    _delivery_message_ids,
    _find_delivery_by_key,
    _http_exception_for_discord_error,
    _post_payloads,
    _resync_one_delivery,
    _serialize,
)


class CountingBot:
    def __init__(self) -> None:
        self.send_calls = 0
        self.edit_calls: list[tuple[str, str]] = []

    async def send_channel_message(
        self, channel_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.send_calls += 1
        return {"id": str(1000 + self.send_calls)}

    async def edit_channel_message(
        self, channel_id: str, message_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.edit_calls.append((channel_id, message_id))
        return {"id": message_id}


def test_discord_400_maps_to_422_not_502() -> None:
    error = DiscordBotAPIError("bad", status_code=400)
    http_error = _http_exception_for_discord_error(error)
    assert http_error.status_code == 422
    assert http_error.detail["code"] == "invalid_payload"


def test_discord_403_maps_to_403() -> None:
    error = DiscordBotAPIError("denied", status_code=403)
    http_error = _http_exception_for_discord_error(error)
    assert http_error.status_code == 403
    assert http_error.detail["code"] == "permission_missing"


def test_discord_404_maps_to_404() -> None:
    error = DiscordBotAPIError("gone", status_code=404)
    http_error = _http_exception_for_discord_error(error)
    assert http_error.status_code == 404
    assert http_error.detail["code"] == "unknown_channel"


def test_discord_429_maps_to_429() -> None:
    error = DiscordBotAPIError("slow", status_code=429)
    http_error = _http_exception_for_discord_error(error)
    assert http_error.status_code == 429
    assert http_error.detail["code"] == "rate_limited"


def test_discord_5xx_maps_to_502() -> None:
    error = DiscordBotAPIError("down", status_code=503)
    http_error = _http_exception_for_discord_error(error)
    assert http_error.status_code == 502


def test_discord_timeout_maps_to_504() -> None:
    error = DiscordBotAPIError("timeout", status_code=None)
    http_error = _http_exception_for_discord_error(error)
    assert http_error.status_code == 504
    assert http_error.detail["code"] == "timeout"


@pytest.mark.anyio
async def test_three_embed_send_persists_all_ids() -> None:
    bot = CountingBot()
    payloads = [{"embeds": [{"description": "a"}]}, {"embeds": [{"description": "b"}]}, {"embeds": [{"description": "c"}]}]
    ids = await _post_payloads(bot, "chan", payloads)
    assert bot.send_calls == 3
    assert ids == ["1001", "1002", "1003"]

    delivery = SimpleNamespace(discord_message_id=None, discord_message_ids=None)
    _apply_sent_ids(delivery, ids)
    assert delivery.discord_message_id == "1001"
    assert delivery.discord_message_ids == ["1001", "1002", "1003"]


def test_duplicate_idempotency_key_finds_existing_row() -> None:
    first = SimpleNamespace(
        channel_id="chan",
        idempotency_key="key-1",
        discord_message_id="111",
        discord_message_ids=["111", "222"],
        status="synced",
    )
    message = SimpleNamespace(deliveries=[first])
    found = _find_delivery_by_key(message, "chan", "key-1")
    assert found is first
    assert _delivery_message_ids(found) == ["111", "222"]


def test_pending_delivery_is_not_serialized_as_missing() -> None:
    delivery = SimpleNamespace(
        id="d-1",
        channel_id="chan",
        discord_message_id=None,
        discord_message_ids=None,
        delivery_type="bot",
        status="pending",
        error=None,
        deployed_version=None,
        owner_feature=OWNER_LIBRARY,
        last_synced_at=None,
        created_at=None,
        idempotency_key="key-1",
    )
    message = SimpleNamespace(
        id="m-1",
        guild_id="g-1",
        name="Test",
        description="",
        content="",
        embed_json=None,
        version=1,
        created_by=None,
        created_at=None,
        updated_at=None,
        deliveries=[delivery],
    )
    result = _serialize(message)
    assert result["sync_status"] == "pending"
    assert result["deliveries"][0]["state"] == "pending"
    assert result["needs_resync"] is False


@pytest.mark.anyio
async def test_resync_edits_all_tracked_message_ids() -> None:
    bot = CountingBot()
    delivery = SimpleNamespace(
        id="d-1",
        channel_id="chan",
        discord_message_id="111",
        discord_message_ids=["111", "222"],
        delivery_type="bot",
        status="synced",
        error=None,
        deployed_version=1,
        owner_feature=OWNER_LIBRARY,
        last_synced_at=None,
        created_at=None,
    )
    message = SimpleNamespace(id="m-1", version=2)
    payloads = [{"content": "a"}, {"content": "b"}]
    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_LIBRARY,
        payload=payloads[0],
        payloads=payloads,
    )
    assert outcome["status"] == "synced"
    assert bot.edit_calls == [("chan", "111"), ("chan", "222")]
    assert bot.send_calls == 0


@pytest.mark.anyio
async def test_resync_skips_in_flight_pending_delivery() -> None:
    bot = CountingBot()
    delivery = SimpleNamespace(
        id="d-1",
        channel_id="chan",
        discord_message_id=None,
        discord_message_ids=None,
        delivery_type="bot",
        status="pending",
        error=None,
        deployed_version=None,
        owner_feature=OWNER_LIBRARY,
        last_synced_at=None,
        created_at=None,
    )
    message = SimpleNamespace(id="m-1", version=1)
    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_LIBRARY,
        payload={"content": "x"},
    )
    assert outcome["status"] == "skipped"
    assert bot.send_calls == 0


def test_http_exception_detail_is_structured() -> None:
    error = DiscordBotAPIError("bad", status_code=403)
    http_error = _http_exception_for_discord_error(error)
    assert isinstance(http_error.detail, dict)
    assert http_error.detail["code"] == "permission_missing"
    assert isinstance(http_error.detail["message"], str)
