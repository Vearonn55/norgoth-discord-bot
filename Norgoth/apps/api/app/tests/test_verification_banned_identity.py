"""Tests for banned-account identity resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.verification_banned_identity import resolve_banned_account_identities


@pytest.mark.anyio
async def test_resolve_uses_ban_snapshot_first() -> None:
    snapshot = SimpleNamespace(
        display_name_snapshot="Display",
        username_snapshot="user",
    )
    accounts = await resolve_banned_account_identities(
        discord_guild_id="111111111111111111",
        matched_user_ids=["222222222222222222"],
        ban_snapshots={"222222222222222222": snapshot},
        bot_client=None,
        lang="en",
    )

    assert len(accounts) == 1
    assert accounts[0].display_name == "Display"
    assert accounts[0].username == "user"
    assert accounts[0].source == "ban_snapshot"


@pytest.mark.anyio
async def test_resolve_falls_back_when_snapshot_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_redis():
        raise RuntimeError("no redis")

    monkeypatch.setattr(
        "app.services.verification_banned_identity.get_redis",
        _no_redis,
    )

    accounts = await resolve_banned_account_identities(
        discord_guild_id="111111111111111111",
        matched_user_ids=["222222222222222222"],
        ban_snapshots={},
        bot_client=None,
        lang="en",
    )

    assert len(accounts) == 1
    assert "222222222222222222" in (accounts[0].display_name or "")
    assert accounts[0].source == "fallback"
