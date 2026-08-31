"""Tests for guild-ban ingest endpoint."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_database_session
from app.main import app


@pytest.mark.anyio
async def test_ingest_guild_ban_upserts_active_ban(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.security.internal_auth.get_settings",
        lambda: SimpleNamespace(
            internal_token="internal-secret",
            discord_bot_token="bot-secret",
        ),
    )

    row_id = uuid4()
    fake_row = type("Row", (), {"id": row_id})()
    session = AsyncMock()

    async def _fake_session():
        yield session

    app.dependency_overrides[get_database_session] = _fake_session

    with patch(
        "app.routes.ingest._guild_ban_service",
    ) as mock_factory:
        service = AsyncMock()
        service.upsert_active_ban.return_value = fake_row
        mock_factory.return_value = service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/internal/ingest/111111111111111111/guild-ban",
                headers={"X-Norgoth-Internal-Token": "internal-secret"},
                json={
                    "discord_user_id": "222222222222222222",
                    "is_active": True,
                    "username": "banned",
                    "display_name": "Banned User",
                    "source": "slash_ban",
                },
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is True
    assert body["id"] == str(row_id)
    service.upsert_active_ban.assert_awaited_once()
    session.commit.assert_awaited_once()
