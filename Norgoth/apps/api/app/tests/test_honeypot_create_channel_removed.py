"""Honeypot API no longer exposes Create Channel."""

from __future__ import annotations

from app.routes.honeypot import router


def test_honeypot_router_has_no_create_channel() -> None:
    paths = [getattr(route, "path", "") for route in router.routes]
    assert not any("create-channel" in path for path in paths)
