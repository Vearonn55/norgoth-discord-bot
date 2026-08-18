"""Tests for the logging-configuration API surface and integrity guarantees.

These lock in the fixes for the rapid-toggle corruption bug:
- a dedicated idempotent state-mutation endpoint (``PATCH .../logging/config``)
  separate from configuration writes (``PUT``);
- request-body validation (``LoggingStateBody`` only carries ``enabled``);
- the database uniqueness constraints that make duplicate channel / event-
  mapping rows impossible, which is what previously let toggling multiply rows.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.models.logging_config import LoggingChannel, LoggingEventMapping
from app.routes.logging_config import (
    LoggingConfigBody,
    LoggingStateBody,
    router as logging_config_router,
)

CONFIG_PATH = "/guilds/{guild_id}/logging/config"


def _registered_operations() -> set[tuple[str, str]]:
    application = FastAPI()
    application.include_router(logging_config_router)
    schema: dict[str, Any] = application.openapi()
    paths: dict[str, Any] = schema["paths"]
    return {
        (path, method.upper())
        for path, operations in paths.items()
        for method in operations
    }


def test_router_exposes_state_patch_endpoint() -> None:
    """The idempotent enable/disable toggle must be a PATCH, not a create."""

    operations = _registered_operations()
    assert (CONFIG_PATH, "PATCH") in operations
    assert (CONFIG_PATH, "PUT") in operations
    assert (CONFIG_PATH, "GET") in operations
    assert ("/guilds/{guild_id}/logging/permissions", "GET") in operations


def test_state_body_only_carries_enabled() -> None:
    """State mutations must not smuggle channels/events (avoids re-create)."""

    body = LoggingStateBody(enabled=False)
    assert body.enabled is False
    assert set(body.model_dump().keys()) == {"enabled"}


def test_state_body_requires_enabled() -> None:
    with pytest.raises(ValidationError):
        LoggingStateBody.model_validate({})


def test_config_body_caps_channels_and_events() -> None:
    """The full-config write keeps its safety caps."""

    too_many_channels = {
        "enabled": True,
        "channels": [
            {"key": f"c{i}", "name": f"chan-{i}"} for i in range(26)
        ],
        "events": [],
    }
    with pytest.raises(ValidationError):
        LoggingConfigBody.model_validate(too_many_channels)


def test_config_body_defaults_are_empty() -> None:
    body = LoggingConfigBody()
    assert body.enabled is True
    assert body.channels == []
    assert body.events == []


def _unique_columns(model: Any) -> set[frozenset[str]]:
    from sqlalchemy import UniqueConstraint

    return {
        frozenset(column.name for column in constraint.columns)
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_router_exposes_channel_sync_and_delete_endpoints() -> None:
    """Per-category Discord rename + delete-log-channel use dedicated routes."""

    operations = _registered_operations()
    channel_path = "/guilds/{guild_id}/logging/channels/{channel_key}"
    delete_path = (
        "/guilds/{guild_id}/logging/channels/{channel_key}/discord-channel"
    )
    assert (channel_path, "PATCH") in operations
    assert (channel_path, "PUT") in operations
    assert (delete_path, "DELETE") in operations


def test_channel_update_body_requires_name() -> None:
    from app.routes.logging_config import LoggingChannelUpdateBody

    with pytest.raises(ValidationError):
        LoggingChannelUpdateBody.model_validate({})

    body = LoggingChannelUpdateBody(name="🔥member-logs", default_color=0xFF0000)
    assert body.name == "🔥member-logs"
    assert body.events == []


def test_catalog_payload_lists_all_supported_groups() -> None:
    """UI merge depends on a complete catalog — not only configured guild rows."""

    from app.services.logging_events import EVENT_GROUPS, catalog_payload

    payload = catalog_payload()
    keys = {group["key"] for group in payload["groups"]}
    assert keys == set(EVENT_GROUPS.keys())
    assert "voice" in keys
    assert "invites" in keys


def test_invite_lifecycle_unique_on_guild_and_code() -> None:
    from app.models.runtime_events import InviteLifecycle

    assert frozenset({"guild_id", "code"}) in _unique_columns(InviteLifecycle)



def test_event_mapping_has_unique_constraint_on_config_and_event() -> None:
    """Prevents duplicate event-mapping rows per configuration."""

    assert (
        frozenset({"logging_configuration_id", "event_type"})
        in _unique_columns(LoggingEventMapping)
    )
