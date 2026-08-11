"""Tests for guild and configuration API schemas and routing."""

from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.v1.router import api_router
from app.schemas.configuration import (
    ConfigurationEnabledRequest,
    ConfigurationUpsertRequest,
)
from app.schemas.guild import GuildUpsertRequest


def _registered_operations() -> set[tuple[str, str]]:
    """Return paths and methods exposed by the V1 API router."""

    application = FastAPI()
    application.include_router(api_router)

    schema: dict[str, Any] = application.openapi()
    paths: dict[str, Any] = schema["paths"]

    return {
        (path, method.upper())
        for path, operations in paths.items()
        for method in operations
        if method.lower()
        in {
            "get",
            "put",
            "post",
            "patch",
            "delete",
            "options",
            "head",
            "trace",
        }
    }


def test_v1_router_contains_guild_routes() -> None:
    """The V1 router should expose approved guild endpoints."""

    operations = _registered_operations()
    guild_path = "/guilds/{discord_guild_id}"

    assert (guild_path, "GET") in operations
    assert (guild_path, "PUT") in operations
    assert (guild_path, "DELETE") in operations


def test_v1_router_contains_configuration_routes() -> None:
    """The V1 router should expose approved configuration endpoints."""

    operations = _registered_operations()
    configuration_path = "/guilds/{discord_guild_id}/configuration"

    assert (configuration_path, "GET") in operations
    assert (configuration_path, "PUT") in operations
    assert (
        f"{configuration_path}/enabled",
        "PATCH",
    ) in operations


def test_guild_upsert_request_accepts_valid_payload() -> None:
    """Valid Discord guild metadata should pass validation."""

    payload = GuildUpsertRequest(
        discord_guild_name="Norgoth Community",
        discord_owner_id="987654321098765432",
    )

    assert payload.discord_guild_name == "Norgoth Community"
    assert payload.discord_owner_id == "987654321098765432"


@pytest.mark.parametrize(
    "invalid_owner_id",
    [
        "",
        "not-a-snowflake",
        "-123",
        "123456789012345678901",
    ],
)
def test_guild_upsert_request_rejects_invalid_owner_id(
    invalid_owner_id: str,
) -> None:
    """Malformed Discord owner IDs should be rejected."""

    with pytest.raises(ValidationError):
        GuildUpsertRequest(
            discord_guild_name="Norgoth Community",
            discord_owner_id=invalid_owner_id,
        )


def test_configuration_upsert_request_defaults() -> None:
    """Configuration payload should apply safe V1 defaults."""

    payload = ConfigurationUpsertRequest(
        verification_channel_id="111111111111111111",
        log_channel_id="222222222222222222",
        verified_role_id="333333333333333333",
        unverified_role_id="444444444444444444",
        member_role_id="555555555555555555",
    )

    assert payload.minimum_account_age_days == 0
    assert payload.session_timeout_seconds == 900
    assert payload.deny_vpn_or_proxy is True
    assert payload.deny_shared_ip is True
    assert payload.enabled is True


@pytest.mark.parametrize(
    ("minimum_account_age_days", "session_timeout_seconds"),
    [
        (-1, 900),
        (3651, 900),
        (0, 59),
        (0, 3601),
    ],
)
def test_configuration_upsert_request_rejects_invalid_ranges(
    minimum_account_age_days: int,
    session_timeout_seconds: int,
) -> None:
    """Invalid age and timeout limits should be rejected."""

    with pytest.raises(ValidationError):
        ConfigurationUpsertRequest(
            verification_channel_id="111111111111111111",
            log_channel_id="222222222222222222",
            verified_role_id="333333333333333333",
            unverified_role_id="444444444444444444",
            member_role_id="555555555555555555",
            minimum_account_age_days=minimum_account_age_days,
            session_timeout_seconds=session_timeout_seconds,
        )


def test_configuration_enabled_request() -> None:
    """The enabled payload should contain only a boolean state."""

    payload = ConfigurationEnabledRequest(enabled=False)

    assert payload.enabled is False
