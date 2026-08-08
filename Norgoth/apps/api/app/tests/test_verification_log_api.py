"""Tests for verification-log schemas and routing."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.models.enums import VerificationStatus
from app.models.verification_log import VerificationLog
from app.schemas.verification_log import (
    VerificationLogResponse,
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


def test_v1_router_contains_verification_log_route() -> None:
    """The V1 router should expose verification-log retrieval."""

    operations = _registered_operations()

    assert (
        "/guilds/{discord_guild_id}/verification-logs",
        "GET",
    ) in operations


def test_verification_log_response_excludes_private_ip_data() -> None:
    """Public log responses should not expose stored IP material."""

    timestamp = datetime.now(UTC)

    verification_log = VerificationLog(
        id=uuid4(),
        guild_id=uuid4(),
        discord_user_id="123456789012345678",
        status=VerificationStatus.FAILED,
        reason="VPN or proxy detected",
        ip_hash="a" * 64,
        ip_encrypted=b"encrypted-ip",
        vpn_or_proxy_detected=True,
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
        created_at=timestamp,
    )

    response = VerificationLogResponse.model_validate(verification_log)
    serialized = response.model_dump()

    assert serialized["discord_user_id"] == "123456789012345678"
    assert serialized["status"] is VerificationStatus.FAILED
    assert serialized["reason"] == "VPN or proxy detected"
    assert serialized["vpn_or_proxy_detected"] is True
    assert "ip_hash" not in serialized
    assert "ip_encrypted" not in serialized
