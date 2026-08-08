"""HTTP tests for verification-log endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_guild_service,
    get_verification_log_service,
)
from app.api.v1.router import api_router
from app.models.discord_guild import DiscordGuild
from app.models.enums import VerificationStatus
from app.models.verification_log import VerificationLog
from app.services.guild_service import GuildService
from app.services.verification_log_service import (
    VerificationLogService,
)

DISCORD_GUILD_ID = "123456789012345678"
DISCORD_OWNER_ID = "987654321098765432"
DISCORD_USER_ID = "111111111111111111"


def _create_test_client(
    *,
    guild_service: GuildService,
    verification_log_service: VerificationLogService,
) -> TestClient:
    """Create an application with overridden dependencies."""

    application = FastAPI()
    application.include_router(api_router)

    application.dependency_overrides[get_guild_service] = lambda: guild_service
    application.dependency_overrides[get_verification_log_service] = lambda: (
        verification_log_service
    )

    return TestClient(application)


def test_list_verification_logs_returns_recent_entries() -> None:
    """GET should return recent verification attempts."""

    timestamp = datetime.now(UTC)
    guild_id = uuid4()

    guild = DiscordGuild(
        id=guild_id,
        discord_guild_id=DISCORD_GUILD_ID,
        discord_guild_name="Norgoth Community",
        discord_owner_id=DISCORD_OWNER_ID,
        created_at=timestamp,
        updated_at=timestamp,
    )

    verification_log = VerificationLog(
        id=uuid4(),
        guild_id=guild_id,
        discord_user_id=DISCORD_USER_ID,
        status=VerificationStatus.SUCCESS,
        reason=None,
        ip_hash="a" * 64,
        ip_encrypted=b"encrypted-ip",
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        blacklisted_guild_detected=False,
        created_at=timestamp,
    )

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    verification_log_service = AsyncMock(spec=VerificationLogService)
    verification_log_service.list_recent.return_value = [verification_log]

    client = _create_test_client(
        guild_service=guild_service,
        verification_log_service=verification_log_service,
    )

    response = client.get(
        f"/guilds/{DISCORD_GUILD_ID}/verification-logs",
        params={"limit": 25},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["discord_user_id"] == DISCORD_USER_ID
    assert response.json()[0]["status"] == "success"
    assert "ip_hash" not in response.json()[0]
    assert "ip_encrypted" not in response.json()[0]

    verification_log_service.list_recent.assert_awaited_once_with(
        guild_id=guild.id,
        limit=25,
    )


def test_list_verification_logs_returns_not_found_for_unknown_guild() -> None:
    """GET should return 404 when the Discord guild is unknown."""

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = None

    verification_log_service = AsyncMock(spec=VerificationLogService)

    client = _create_test_client(
        guild_service=guild_service,
        verification_log_service=verification_log_service,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}/verification-logs")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Discord guild not found.",
    }
    verification_log_service.list_recent.assert_not_awaited()


def test_list_verification_logs_uses_default_limit() -> None:
    """GET should request 50 logs when no limit is supplied."""

    timestamp = datetime.now(UTC)

    guild = DiscordGuild(
        id=uuid4(),
        discord_guild_id=DISCORD_GUILD_ID,
        discord_guild_name="Norgoth Community",
        discord_owner_id=DISCORD_OWNER_ID,
        created_at=timestamp,
        updated_at=timestamp,
    )

    guild_service = AsyncMock(spec=GuildService)
    guild_service.get_by_discord_guild_id.return_value = guild

    verification_log_service = AsyncMock(spec=VerificationLogService)
    verification_log_service.list_recent.return_value = []

    client = _create_test_client(
        guild_service=guild_service,
        verification_log_service=verification_log_service,
    )

    response = client.get(f"/guilds/{DISCORD_GUILD_ID}/verification-logs")

    assert response.status_code == 200
    assert response.json() == []

    verification_log_service.list_recent.assert_awaited_once_with(
        guild_id=guild.id,
        limit=50,
    )


def test_list_verification_logs_rejects_invalid_limit() -> None:
    """GET should reject limits outside the supported range."""

    guild_service = AsyncMock(spec=GuildService)
    verification_log_service = AsyncMock(spec=VerificationLogService)

    client = _create_test_client(
        guild_service=guild_service,
        verification_log_service=verification_log_service,
    )

    response = client.get(
        f"/guilds/{DISCORD_GUILD_ID}/verification-logs",
        params={"limit": 101},
    )

    assert response.status_code == 422
    guild_service.get_by_discord_guild_id.assert_not_awaited()
    verification_log_service.list_recent.assert_not_awaited()
