"""Feed repair: channel names, permission helper usage, mocked recreate."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.discord.bot_rest import (
    DiscordBotAPIError,
    FEED_EVERYONE_DENY,
    PERM_SEND_MESSAGES,
    feed_channel_permission_overwrites,
)
from app.services.feed_repair import _window_channel_name, repair_feed_channels


def test_window_channel_names() -> None:
    assert _window_channel_name("daily") == "feed-daily"
    assert _window_channel_name("all_time") == "feed-all-time"


def test_feed_overwrites_deny_send_for_everyone() -> None:
    overs = feed_channel_permission_overwrites("g1", bot_user_id="b1")
    everyone = overs[0]
    assert everyone["id"] == "g1"
    assert int(everyone["deny"]) & PERM_SEND_MESSAGES
    assert int(everyone["deny"]) == FEED_EVERYONE_DENY


@pytest.mark.anyio
async def test_repair_recreates_missing_channel_then_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing channel → create once; second repair creates zero channels."""

    config: dict[str, Any] = {
        "enabled": True,
        "upvote_emoji": "👍",
        "downvote_emoji": "👎",
        "source_channel_ids": ["src1"],
        "display_limit": 10,
        "min_net_score": 1,
        "refresh_interval_minutes": 15,
        "windows": {
            "daily": {
                "channel_id": "old-ch",
                "enabled": True,
                "norgoth_managed": True,
            },
            "weekly": {"channel_id": None, "enabled": False},
            "monthly": {"channel_id": None, "enabled": False},
            "all_time": {"channel_id": None, "enabled": False},
        },
    }

    async def fake_load(_guild_id: str) -> dict[str, Any]:
        return config

    save_calls: list[dict[str, Any]] = []

    async def fake_save(
        guild_id: str, key: str, payload: dict[str, Any], enabled: bool = True
    ) -> None:
        snapshot = {
            **payload,
            "windows": {
                w: dict(cfg) for w, cfg in (payload.get("windows") or {}).items()
            },
        }
        save_calls.append({"guild_id": guild_id, "key": key, "payload": snapshot})
        # Mutate in place without clear()+update(same ref) wiping the live dict.
        config["windows"] = snapshot["windows"]
        for k, v in snapshot.items():
            if k != "windows":
                config[k] = v

    rebuild_calls = 0

    async def fake_rebuild(session, *, guild_id, window, config=None, force=False):
        nonlocal rebuild_calls
        rebuild_calls += 1
        return {
            "ok": True,
            "window": window,
            "messages_deleted": 0,
            "messages_restored": 2,
            "messages_updated": 0,
        }

    async def fake_audit(*_a, **_k) -> None:
        return None

    class FakeSettings:
        discord_bot_token = "token"

    created_channels: list[str] = []
    get_channel_calls = 0

    class FakeBot:
        def __init__(self, *_a, **_k) -> None:
            pass

        async def get_bot_user(self) -> dict[str, str]:
            return {"id": "bot99"}

        async def get_channel(self, channel_id: str) -> dict[str, str]:
            nonlocal get_channel_calls
            get_channel_calls += 1
            # First repair: old channel 404s. Later: new channel exists.
            if channel_id == "old-ch":
                raise DiscordBotAPIError("missing", status_code=404)
            return {"id": channel_id}

        async def create_guild_channel(
            self,
            guild_id: str,
            *,
            name: str,
            channel_type: int,
            parent_id=None,
            permission_overwrites=None,
            reason: str | None = None,
        ) -> dict[str, str]:
            assert name == "feed-daily"
            assert permission_overwrites
            deny = int(permission_overwrites[0]["deny"])
            assert deny & PERM_SEND_MESSAGES
            created_channels.append(name)
            return {"id": "new-ch"}

        async def edit_channel(self, channel_id: str, **_kwargs) -> dict[str, str]:
            return {"id": channel_id}

    class FakeHttp:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self) -> "FakeHttp":
            return self

        async def __aexit__(self, *a) -> None:
            return None

    monkeypatch.setattr(
        "app.services.feed_repair.get_settings", lambda: FakeSettings()
    )
    monkeypatch.setattr(
        "app.services.feed_repair.load_merged_feed_config", fake_load
    )
    monkeypatch.setattr("app.services.feed_repair.save_config", fake_save)
    monkeypatch.setattr(
        "app.services.feed_repair.rebuild_feed_window", fake_rebuild
    )
    monkeypatch.setattr("app.services.feed_repair.record_audit", fake_audit)
    monkeypatch.setattr("app.services.feed_repair.DiscordBotClient", FakeBot)
    monkeypatch.setattr("app.services.feed_repair.httpx.AsyncClient", FakeHttp)

    session = MagicMock()
    session.commit = AsyncMock()
    first = await repair_feed_channels(session, guild_id="guild1")
    assert first["success"] is True
    assert first["channels_created"] == 1
    assert first["messages_restored"] == 2
    assert created_channels == ["feed-daily"]
    assert config["windows"]["daily"]["channel_id"] == "new-ch"
    assert rebuild_calls == 1

    # Second repair: channel exists → no create, still syncs.
    second = await repair_feed_channels(session, guild_id="guild1")
    assert second["success"] is True
    assert second["channels_created"] == 0
    assert len(created_channels) == 1
    assert rebuild_calls == 2
