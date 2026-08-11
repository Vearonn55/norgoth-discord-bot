"""Tests for the embed-draft delete dependency guard."""

from types import SimpleNamespace
from typing import Any

import pytest

import app.routes.embed_messages as em


def _message(*, message_id: str, delivery_ids: list[str]) -> Any:
    return SimpleNamespace(
        id=message_id,
        deliveries=[SimpleNamespace(id=did) for did in delivery_ids],
    )


@pytest.mark.anyio
async def test_no_dependencies_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_menus(_guild: str) -> list[dict[str, Any]]:
        return []

    async def fake_config(_guild: str, _key: str) -> dict[str, Any] | None:
        return None

    monkeypatch.setattr(em, "read_menus", fake_menus)
    monkeypatch.setattr(em, "load_config", fake_config)

    deps = await em._draft_dependencies(
        "g-1", _message(message_id="m-1", delivery_ids=["d-1"])
    )
    assert deps == []


@pytest.mark.anyio
async def test_role_menu_binding_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_menus(_guild: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "menu-1",
                "name": "Colors",
                "binding_type": "embed_message",
                "embed_delivery_id": "d-1",
            }
        ]

    async def fake_config(_guild: str, _key: str) -> dict[str, Any] | None:
        return None

    monkeypatch.setattr(em, "read_menus", fake_menus)
    monkeypatch.setattr(em, "load_config", fake_config)

    deps = await em._draft_dependencies(
        "g-1", _message(message_id="m-1", delivery_ids=["d-1"])
    )
    assert deps == [{"feature": "self_assignable_role", "label": "Colors"}]


@pytest.mark.anyio
async def test_welcome_leave_reference_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_menus(_guild: str) -> list[dict[str, Any]]:
        return []

    async def fake_config(_guild: str, _key: str) -> dict[str, Any] | None:
        return {
            "welcome_embed_message_id": "m-1",
            "leave_embed_message_id": "m-1",
        }

    monkeypatch.setattr(em, "read_menus", fake_menus)
    monkeypatch.setattr(em, "load_config", fake_config)

    deps = await em._draft_dependencies(
        "g-1", _message(message_id="m-1", delivery_ids=[])
    )
    features = {d["feature"] for d in deps}
    assert features == {"welcome", "leave"}
