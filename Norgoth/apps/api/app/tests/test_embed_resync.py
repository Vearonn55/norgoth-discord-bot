"""Tests for deployment-driven, owner-aware embed Re-Sync semantics."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.integrations.discord.bot_rest import DiscordBotAPIError
from app.routes.embed_messages import OWNER_LIBRARY, OWNER_SAR, _resync_one_delivery


class FakeBot:
    """Records edit/send calls; optionally 404s on edit to simulate deletion."""

    def __init__(self, *, edit_404: bool = False) -> None:
        self.edit_calls: list[tuple[str, str]] = []
        self.send_calls: list[str] = []
        self._edit_404 = edit_404

    async def edit_channel_message(
        self, channel_id: str, message_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.edit_calls.append((channel_id, message_id))
        if self._edit_404:
            raise DiscordBotAPIError(status_code=404, message="gone")
        return {"id": message_id}

    async def send_channel_message(
        self, channel_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.send_calls.append(channel_id)
        return {"id": "999"}


def _delivery(**kwargs: Any) -> Any:
    base = {
        "id": "d-1",
        "channel_id": "chan",
        "discord_message_id": "111",
        "delivery_type": "bot",
        "status": "synced",
        "error": None,
        "deployed_version": 1,
        "owner_feature": OWNER_LIBRARY,
        "last_synced_at": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _message(version: int = 1) -> Any:
    return SimpleNamespace(id="m-1", version=version)


@pytest.mark.anyio
async def test_current_delivery_is_skipped_idempotent() -> None:
    bot = FakeBot()
    delivery = _delivery(status="synced", deployed_version=2)
    message = _message(version=2)

    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_LIBRARY,
        payload={"content": "x"},
    )

    assert outcome["status"] == "skipped"
    assert bot.edit_calls == []
    assert bot.send_calls == []


@pytest.mark.anyio
async def test_stale_live_delivery_is_edited_in_place() -> None:
    bot = FakeBot()
    delivery = _delivery(status="synced", deployed_version=1)
    message = _message(version=2)

    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_LIBRARY,
        payload={"content": "x"},
    )

    assert outcome["status"] == "synced"
    assert bot.edit_calls == [("chan", "111")]
    assert bot.send_calls == []
    assert delivery.deployed_version == 2


@pytest.mark.anyio
async def test_missing_library_message_is_recreated() -> None:
    bot = FakeBot()
    delivery = _delivery(
        status="message_missing", discord_message_id=None, deployed_version=1
    )
    message = _message(version=2)

    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_LIBRARY,
        payload={"content": "x"},
    )

    assert outcome["status"] == "synced"
    assert bot.send_calls == ["chan"]
    assert delivery.discord_message_id == "999"
    assert delivery.status == "synced"


@pytest.mark.anyio
async def test_missing_sar_message_flagged_for_feature_repair() -> None:
    bot = FakeBot()
    delivery = _delivery(
        status="message_missing", discord_message_id=None, owner_feature=OWNER_SAR
    )
    message = _message(version=2)

    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_SAR,
        payload={"content": "x"},
    )

    assert outcome["status"] == "needs_feature_repair"
    # Never recreates a plain embed for a component-bound deployment.
    assert bot.send_calls == []
    assert delivery.status == "message_missing"


@pytest.mark.anyio
async def test_edit_404_falls_through_to_recreate_for_library() -> None:
    bot = FakeBot(edit_404=True)
    delivery = _delivery(status="synced", deployed_version=1)
    message = _message(version=2)

    outcome = await _resync_one_delivery(
        bot=bot,
        delivery=delivery,
        message=message,
        owner=OWNER_LIBRARY,
        payload={"content": "x"},
    )

    assert outcome["status"] == "synced"
    assert bot.edit_calls == [("chan", "111")]
    assert bot.send_calls == ["chan"]
    assert delivery.discord_message_id == "999"
