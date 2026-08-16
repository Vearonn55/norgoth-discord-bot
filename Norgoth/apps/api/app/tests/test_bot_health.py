from app.routes.bot import build_bot_health_payload


def test_bot_health_online_when_heartbeat_and_connected() -> None:
    payload = build_bot_health_payload(
        "2026-08-16T06:00:00+00:00",
        {"connected": True, "guilds": [{"id": "1", "name": "secret"}]},
    )
    assert payload["connected"] is True
    assert payload["stale"] is False
    assert "guilds" not in payload
    assert "status" not in payload


def test_bot_health_offline_without_heartbeat() -> None:
    payload = build_bot_health_payload(None, {"connected": False})
    assert payload["connected"] is False
    assert payload["stale"] is False


def test_bot_health_stale_when_status_connected_but_heartbeat_expired() -> None:
    payload = build_bot_health_payload(None, {"connected": True})
    assert payload["connected"] is False
    assert payload["stale"] is True
