"""Ingest routes for late actor PATCH and invite lifecycle."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.routes.ingest import router as ingest_router


def _paths() -> dict[str, Any]:
    application = FastAPI()
    application.include_router(ingest_router)
    schema: dict[str, Any] = application.openapi()
    return schema["paths"]


def test_ingest_exposes_server_event_patch_and_invite_lifecycle() -> None:
    paths = _paths()
    patch_path = "/internal/ingest/{guild_id}/server-event/{source_event_id}"
    assert patch_path in paths
    assert "patch" in paths[patch_path]
    assert "/internal/ingest/{guild_id}/invite-lifecycle" in paths
    assert "post" in paths["/internal/ingest/{guild_id}/invite-lifecycle"]
    snapshot = "/internal/ingest/{guild_id}/invite-lifecycle/snapshot"
    vanished = "/internal/ingest/{guild_id}/invite-lifecycle/recent-vanished"
    assert snapshot in paths
    assert vanished in paths
    assert "get" in paths[vanished]
