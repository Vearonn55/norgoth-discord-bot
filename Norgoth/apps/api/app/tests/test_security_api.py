"""Tests for security-list API schemas and routing."""

from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.v1.router import api_router
from app.models.enums import UserListType
from app.schemas.security import (
    HighRiskGuildUpsertRequest,
    UserListUpsertRequest,
)


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


def test_v1_router_contains_user_list_routes() -> None:
    """The V1 router should expose user-list management endpoints."""

    operations = _registered_operations()
    base_path = "/guilds/{discord_guild_id}/user-list"

    assert (base_path, "GET") in operations
    assert (
        f"{base_path}/{{discord_user_id}}",
        "PUT",
    ) in operations
    assert (
        f"{base_path}/{{discord_user_id}}",
        "DELETE",
    ) in operations


def test_v1_router_has_no_blacklisted_guild_routes() -> None:
    """The legacy guild-blacklist endpoints must be fully removed."""

    operations = _registered_operations()

    assert not any(
        "/blacklisted-guilds" in path for path, _ in operations
    )


def test_v1_router_contains_high_risk_guild_routes() -> None:
    """The V1 router should expose high-risk-guild endpoints."""

    operations = _registered_operations()
    base_path = "/guilds/{discord_guild_id}/high-risk-guilds"

    assert (base_path, "GET") in operations
    assert (
        f"{base_path}/{{high_risk_discord_guild_id}}",
        "PUT",
    ) in operations
    assert (
        f"{base_path}/{{high_risk_discord_guild_id}}",
        "DELETE",
    ) in operations


def test_user_list_upsert_request_accepts_whitelist() -> None:
    """Whitelist payloads should pass validation."""

    payload = UserListUpsertRequest(
        list_type=UserListType.WHITELIST,
        reason="Trusted member",
    )

    assert payload.list_type is UserListType.WHITELIST
    assert payload.reason == "Trusted member"


def test_user_list_upsert_request_accepts_blacklist() -> None:
    """Blacklist payloads should pass validation."""

    payload = UserListUpsertRequest(
        list_type=UserListType.BLACKLIST,
        reason=None,
    )

    assert payload.list_type is UserListType.BLACKLIST
    assert payload.reason is None


def test_user_list_upsert_request_rejects_invalid_type() -> None:
    """Unknown list types should be rejected."""

    with pytest.raises(ValidationError):
        UserListUpsertRequest.model_validate(
            {
                "list_type": "unknown",
                "reason": None,
            }
        )


def test_user_list_upsert_request_rejects_long_reason() -> None:
    """Reasons longer than 200 characters should be rejected."""

    with pytest.raises(ValidationError):
        UserListUpsertRequest(
            list_type=UserListType.BLACKLIST,
            reason="x" * 201,
        )


def test_high_risk_guild_request_accepts_reason() -> None:
    """A valid high-risk reason should pass validation."""

    payload = HighRiskGuildUpsertRequest(
        reason="Known raid community",
    )

    assert payload.reason == "Known raid community"


def test_high_risk_guild_request_allows_empty_reason() -> None:
    """A high-risk guild entry may omit its reason."""

    payload = HighRiskGuildUpsertRequest()

    assert payload.reason is None
