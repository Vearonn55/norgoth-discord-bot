"""HTTP tests for verification log listing and manual-review queue API."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.dependencies import get_guild_service, get_settings, get_verification_log_service
from app.api.v1.verification_logs import router as verification_logs_router
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.models.enums import VerificationStatus
from app.models.verification_attempt import VerificationAttempt
from app.repositories.verification_log_repository import VerificationLogRepository
from app.services.views import VerificationAttemptView

GUILD_DISCORD_ID = "111111111111111111"
OTHER_GUILD_DISCORD_ID = "222222222222222222"
INTERNAL_GUILD_ID = uuid4()
ATTEMPT_ID = uuid4()
USER_ID = "123456789012345678"


def _attempt_view(*, guild_id=INTERNAL_GUILD_ID) -> VerificationAttemptView:
    return VerificationAttemptView(
        id=ATTEMPT_ID,
        guild_id=guild_id,
        discord_user_id=USER_ID,
        status=VerificationStatus.MANUAL_REVIEW,
        reason="high_risk_guild",
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        high_risk_guild_detected=True,
        matched_high_risk_guild_ids=("900000000000000001",),
        reviewed_by=None,
        reviewed_at=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class _FakeGuildService:
    async def get_by_discord_guild_id(self, discord_guild_id: str):
        if discord_guild_id == GUILD_DISCORD_ID:
            return SimpleNamespace(id=INTERNAL_GUILD_ID, discord_guild_id=GUILD_DISCORD_ID)
        return None


class _FakeVerificationLogService:
    def __init__(self, *, views: list[VerificationAttemptView], total: int) -> None:
        self._views = views
        self._total = total
        self.last_list_kwargs: dict[str, object] | None = None

    async def list_page(self, **kwargs):
        self.last_list_kwargs = kwargs
        return self._views, self._total

    async def get_attempt(self, **kwargs):
        return None


def _settings() -> Settings:
    return Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment="test",
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=None,
        database_echo=False,
        auth_enforced=False,
        discord_client_id="client-id",
        discord_client_secret="client-secret",
        discord_redirect_uri="https://example.test/callback",
        dashboard_public_url="https://example.test",
    )


def _build_client(
    *,
    verification_log_service: _FakeVerificationLogService,
) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(verification_logs_router, prefix="/api/v1")

    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_guild_service] = lambda: _FakeGuildService()
    app.dependency_overrides[get_verification_log_service] = (
        lambda: verification_log_service
    )

    return TestClient(app)


def test_list_pending_manual_review_returns_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pending queue rows are returned for the selected guild."""

    service = _FakeVerificationLogService(views=[_attempt_view()], total=1)

    async def _no_identities(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(
        "app.api.v1.verification_logs._resolve_identities",
        _no_identities,
    )

    client = _build_client(verification_log_service=service)
    response = client.get(
        f"/api/v1/guilds/{GUILD_DISCORD_ID}/verification-logs",
        params={"status": "manual_review", "limit": 10, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == str(ATTEMPT_ID)
    assert item["discord_user_id"] == USER_ID
    assert item["status"] == "manual_review"
    assert item["display_name"] is None
    assert item["avatar_url"] is None
    assert service.last_list_kwargs is not None
    assert service.last_list_kwargs["status"] is VerificationStatus.MANUAL_REVIEW
    assert service.last_list_kwargs["guild_id"] == INTERNAL_GUILD_ID


def test_list_unknown_guild_returns_404() -> None:
    service = _FakeVerificationLogService(views=[], total=0)
    client = _build_client(verification_log_service=service)

    response = client.get(
        f"/api/v1/guilds/{OTHER_GUILD_DISCORD_ID}/verification-logs",
        params={"status": "manual_review"},
    )

    assert response.status_code == 404


def test_apply_filters_requires_unreviewed_manual_review_rows() -> None:
    """Pending list queries exclude resolved manual-review attempts."""

    repository = VerificationLogRepository(AsyncMock())
    statement = select(VerificationAttempt)
    filtered = repository._apply_filters(
        statement,
        status=VerificationStatus.MANUAL_REVIEW,
        query=None,
    )
    compiled = str(
        filtered.whereclause.compile(compile_kwargs={"literal_binds": True})
    )
    assert "manual_review" in compiled
    assert "reviewed_at IS NULL" in compiled
