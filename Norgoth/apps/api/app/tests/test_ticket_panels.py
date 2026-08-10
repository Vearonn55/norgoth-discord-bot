"""Ticket panel schema + lazy category backfill tests.

Panels are Postgres-backed (``ticket_panels`` feature) with a Redis snapshot.
Panels created before per-panel routing existed have no ``open_category_id``
key, so ``read_ticket_panels`` must inherit the guild's legacy global tickets
config for that absent key only (never overriding an admin's explicit null).
Any legacy ``closed_log_channel_id`` is dropped: closed-ticket logging is now
handled by the central Logging Configurations wizard (Tickets group).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.routes import tickets

GUILD_ID = "123456789012345678"
GLOBAL_CATEGORY = "111111111111111111"
GLOBAL_LOG = "222222222222222222"


class FakeRedis:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def aclose(self) -> None:
        return None


def _patch(monkeypatch: pytest.MonkeyPatch, panels: list[dict[str, Any]]) -> None:
    panels_payload = json.dumps({"panels": panels})

    async def _fake_get_redis() -> FakeRedis:
        return FakeRedis({})

    async def _fake_read_raw(
        guild_id: str, feature: str, redis_client: Any = None
    ) -> str | None:
        if feature == "ticket_panels":
            return panels_payload
        if feature == "tickets":
            return json.dumps(
                {"category_id": GLOBAL_CATEGORY, "log_channel_id": GLOBAL_LOG}
            )
        return None

    monkeypatch.setattr(tickets, "get_redis", _fake_get_redis)
    monkeypatch.setattr(tickets, "read_raw", _fake_read_raw)


def test_ticket_panel_model_accepts_embed_message_id() -> None:
    panel = tickets.TicketPanel(
        name="Support",
        embed_message_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert panel.embed_message_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    dumped = panel.model_dump()
    assert dumped["embed_message_id"] == panel.embed_message_id
    assert dumped["message_source"] == "embed"


def test_ticket_panel_model_defaults_embed_message_id_none() -> None:
    panel = tickets.TicketPanel(name="Support")
    assert panel.embed_message_id is None
    assert panel.message_source == "embed"
    assert panel.text_content == ""


def test_ticket_panel_model_dropped_closed_log_field() -> None:
    panel = tickets.TicketPanel(name="Support")
    assert panel.open_category_id is None
    # The per-panel closed-ticket log channel was removed from the schema.
    assert "closed_log_channel_id" not in tickets.TicketPanel.model_fields

    configured = tickets.TicketPanel(
        name="Support",
        open_category_id=GLOBAL_CATEGORY,
    )
    assert configured.open_category_id == GLOBAL_CATEGORY
    assert not hasattr(configured, "closed_log_channel_id")


@pytest.mark.anyio
async def test_absent_category_backfills_and_log_field_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        [{"id": "p1", "name": "Legacy panel", "closed_log_channel_id": GLOBAL_LOG}],
    )

    panels = await tickets.read_ticket_panels(GUILD_ID)

    assert panels[0]["open_category_id"] == GLOBAL_CATEGORY
    # Any legacy per-panel log channel is dropped on read.
    assert "closed_log_channel_id" not in panels[0]
    assert panels[0]["message_source"] == "embed"


@pytest.mark.anyio
async def test_explicit_null_category_is_not_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        [
            {
                "id": "p1",
                "name": "Cleared panel",
                "open_category_id": None,
            }
        ],
    )

    panels = await tickets.read_ticket_panels(GUILD_ID)

    # Key is present, so the admin's explicit clearing is preserved.
    assert panels[0]["open_category_id"] is None


@pytest.mark.anyio
async def test_panel_specific_category_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        [
            {
                "id": "p1",
                "name": "Sales",
                "open_category_id": "333333333333333333",
            }
        ],
    )

    panels = await tickets.read_ticket_panels(GUILD_ID)

    assert panels[0]["open_category_id"] == "333333333333333333"


@pytest.mark.anyio
async def test_legacy_embed_id_infers_embed_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(
        monkeypatch,
        [
            {
                "id": "p1",
                "name": "With draft",
                "embed_message_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "open_category_id": GLOBAL_CATEGORY,
            }
        ],
    )

    panels = await tickets.read_ticket_panels(GUILD_ID)
    assert panels[0]["message_source"] == "embed"
