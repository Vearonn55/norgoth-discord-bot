"""Unit tests for audit-detail sanitization, redaction, and list/detail shapes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.security.internal_auth import require_internal_token
from app.services.audit_detail import (
    PAYLOAD_MAX_BYTES,
    bound_payload,
    prepare_event_payload,
    sanitize_detail,
    serialize_event_detail,
    serialize_event_summary,
)


def _v1_detail(**overrides):
    payload = {
        "schema_version": 1,
        "event_type": "channel_update",
        "target": {"kind": "channel", "id": "99", "name": "general", "type": "text"},
        "actor": {"id": "8", "name": "Mod"},
        "source": "discord_gateway",
        "reason": None,
        "correlation_id": None,
        "field_changes": [
            {"field": "name", "previous": "old", "next": "new"},
        ],
        "permission_changes": {
            "kind": "overwrites",
            "items": [
                {
                    "target_kind": "role",
                    "target_id": "10",
                    "target_name": "@Mods",
                    "permission": "view_channel",
                    "previous": "allow",
                    "next": "deny",
                    "change": "transition",
                    "unknown_mask": None,
                }
            ],
            "category_synced": False,
        },
        "truncated": False,
    }
    payload.update(overrides)
    return payload


def test_prepare_event_stores_versioned_detail() -> None:
    payload, has_detail = prepare_event_payload(
        {"description": "Channel updated", "fields": {"Name": "a → b"}, "detail": _v1_detail()}
    )
    assert has_detail is True
    assert payload["detail"]["schema_version"] == 1
    assert payload["detail"]["field_changes"][0]["field"] == "name"


def test_legacy_payload_has_no_detail() -> None:
    payload, has_detail = prepare_event_payload(
        {"description": "old", "fields": {"Topic": "updated"}, "detail": None}
    )
    assert has_detail is False
    assert payload["detail"] is None


def test_sensitive_keys_are_stripped() -> None:
    payload, _has_detail = prepare_event_payload(
        {
            "description": "x",
            "fields": {
                "token": "super-secret",
                "webhook_url": "https://discord.com/api/webhooks/1/abc",
                "Name": "ok",
            },
            "detail": _v1_detail(
                field_changes=[
                    {"field": "name", "previous": "a", "next": "b"},
                    {"field": "token", "previous": "x", "next": "y"},
                ]
            ),
        }
    )
    assert "token" not in payload["fields"]
    assert "webhook_url" not in payload["fields"]
    assert payload["fields"]["Name"] == "ok"
    fields = {item["field"] for item in payload["detail"]["field_changes"]}
    assert fields == {"name"}


def test_oversized_payload_is_truncated() -> None:
    huge = "t" * 800
    changes = [{"field": "topic", "previous": huge, "next": huge} for _ in range(32)]
    items = [
        {
            "target_kind": "role",
            "target_id": str(index),
            "target_name": "r" * 80,
            "permission": "view_channel",
            "previous": "inherit",
            "next": "allow",
            "change": "transition",
        }
        for index in range(200)
    ]
    raw = {
        "description": "x" * 1000,
        "fields": {f"k{i}": "v" * 200 for i in range(40)},
        "detail": _v1_detail(field_changes=changes, permission_changes={"kind": "overwrites", "items": items}),
    }
    payload, has_detail = prepare_event_payload(raw)
    encoded = __import__("json").dumps(payload, default=str)
    assert len(encoded.encode("utf-8")) <= PAYLOAD_MAX_BYTES
    assert payload["detail"]["truncated"] is True or has_detail


def test_list_summary_omits_payload() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        source_event_id="abc",
        category="channel",
        action="Channel updated",
        event_type="channel_update",
        actor_id="8",
        actor_name="Mod",
        created_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        has_detail=True,
        payload={"description": "hi", "fields": {"secret": "nope"}, "detail": _v1_detail()},
    )
    summary = serialize_event_summary(row)
    assert "payload" not in summary
    assert "field_changes" not in summary
    assert "detail" not in summary
    assert summary["has_detail"] is True
    assert summary["action"] == "Channel updated"


def test_detail_legacy_flag_for_schema_zero() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        source_event_id="abc",
        category="channel",
        action="Channel updated",
        event_type="channel_update",
        actor_id=None,
        actor_name=None,
        created_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        has_detail=False,
        payload={"description": "hi", "fields": {"Topic": "updated"}, "detail": None},
    )
    body = serialize_event_detail(row)
    assert body["legacy"] is True
    assert body["detail"] is None
    assert body["fields"]["Topic"] == "updated"


def test_unknown_field_keys_dropped() -> None:
    sanitized = sanitize_detail(
        _v1_detail(field_changes=[{"field": "internal_exception", "previous": "a", "next": "b"}])
    )
    assert sanitized is not None
    assert sanitized["field_changes"] == []


def test_bound_payload_helper_marks_truncated() -> None:
    payload = {
        "description": "x",
        "fields": {},
        "detail": _v1_detail(
            field_changes=[{"field": "topic", "previous": "a" * 400, "next": "b" * 400} for _ in range(32)]
        ),
    }
    bounded = bound_payload(payload)
    encoded = __import__("json").dumps(bounded, default=str)
    assert len(encoded.encode("utf-8")) <= PAYLOAD_MAX_BYTES


@pytest.mark.asyncio
async def test_detail_404_when_event_belongs_to_another_guild() -> None:
    from app.routes.server_logs import get_event_log_detail

    class _Result:
        def scalar_one_or_none(self):
            return None

    class _Session:
        async def execute(self, _query):
            return _Result()

    with pytest.raises(HTTPException) as exc:
        await get_event_log_detail("111111111111111111", uuid4(), _Session())  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_internal_ingest_requires_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.internal_auth.get_settings",
        lambda: SimpleNamespace(internal_token="internal-secret", discord_bot_token="bot-secret"),
    )
    application = FastAPI()

    @application.post(
        "/internal/ingest/{guild_id}/server-event",
        dependencies=[Depends(require_internal_token)],
    )
    def _ingest(guild_id: str) -> dict[str, str]:
        return {"id": guild_id}

    client = TestClient(application)
    assert client.post("/internal/ingest/123456789012345678/server-event", json={}).status_code == 401
    allowed = client.post(
        "/internal/ingest/123456789012345678/server-event",
        headers={"X-Norgoth-Internal-Token": "internal-secret"},
        json={"event_type": "channel_update"},
    )
    assert allowed.status_code == 200
