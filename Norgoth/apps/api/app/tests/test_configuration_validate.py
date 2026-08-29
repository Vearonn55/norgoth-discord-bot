"""Route-level tests for verification configuration validate/save contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.configuration import (
    create_or_update_configuration,
    validate_verification_configuration,
)
from app.models.enums import RiskAction
from app.schemas.configuration import ConfigurationUpsertRequest
from app.services.verification_discord_validate import VerificationDiscordValidation
from app.services.views import ConfigurationView


def _draft_payload() -> ConfigurationUpsertRequest:
    return ConfigurationUpsertRequest(
        verification_channel_id="100",
        log_channel_id="101",
        unverified_role_id="200",
        member_role_id="201",
        enabled=True,
    )


def _persisted_config(guild_id) -> ConfigurationView:
    return ConfigurationView(
        id=uuid4(),
        guild_id=guild_id,
        verification_channel_id="100",
        log_channel_id="101",
        unverified_role_id="200",
        member_role_id="201",
        manual_review_role_id="",
        minimum_account_age_days=0,
        session_timeout_seconds=900,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        vpn_or_proxy_action=RiskAction.DENY,
        shared_ip_action=RiskAction.DENY,
        enabled=True,
        panel_message_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_validate_without_body_requires_persisted_bindings() -> None:
    """Pre-save validate (no body) fails when PostgreSQL has no complete config."""

    guild_id = uuid4()
    guild = SimpleNamespace(id=guild_id)
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(return_value=guild),
    )
    configuration_service = SimpleNamespace(get_by_guild_id=AsyncMock(return_value=None))
    bot_client = object()

    response = await validate_verification_configuration(
        discord_guild_id="99",
        guild_service=guild_service,
        configuration_service=configuration_service,
        bot_client=bot_client,
        payload=None,
    )

    assert response.ok is False
    assert response.setup_state == "not_configured"
    assert response.issues[0]["code"] == "verification_not_configured"


@pytest.mark.asyncio
async def test_validate_with_draft_payload_skips_persisted_incomplete_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Draft POST validate validates submitted bindings without a prior save."""

    guild_id = uuid4()
    guild = SimpleNamespace(id=guild_id)
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(return_value=guild),
    )
    configuration_service = SimpleNamespace(get_by_guild_id=AsyncMock(return_value=None))
    bot_client = object()

    async def fake_validate(**kwargs):  # noqa: ANN003
        assert kwargs["configuration"].verification_channel_id == "100"
        return VerificationDiscordValidation(ok=True, setup_state="active", issues=[])

    monkeypatch.setattr(
        "app.api.v1.configuration.validate_verification_discord_resources",
        fake_validate,
    )

    response = await validate_verification_configuration(
        discord_guild_id="99",
        guild_service=guild_service,
        configuration_service=configuration_service,
        bot_client=bot_client,
        payload=_draft_payload(),
    )

    assert response.ok is True
    configuration_service.get_by_guild_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_without_body_uses_persisted_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guild_id = uuid4()
    guild = SimpleNamespace(id=guild_id)
    persisted = _persisted_config(guild_id)
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(return_value=guild),
    )
    configuration_service = SimpleNamespace(
        get_by_guild_id=AsyncMock(return_value=persisted),
    )
    bot_client = object()

    async def fake_validate(**kwargs):  # noqa: ANN003
        assert kwargs["configuration"] is persisted
        return VerificationDiscordValidation(ok=True, setup_state="active", issues=[])

    monkeypatch.setattr(
        "app.api.v1.configuration.validate_verification_discord_resources",
        fake_validate,
    )

    response = await validate_verification_configuration(
        discord_guild_id="99",
        guild_service=guild_service,
        configuration_service=configuration_service,
        bot_client=bot_client,
        payload=None,
    )

    assert response.ok is True
    configuration_service.get_by_guild_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_put_rejects_when_bot_client_missing() -> None:
    guild_id = uuid4()
    guild = SimpleNamespace(id=guild_id)
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(return_value=guild),
    )
    configuration_service = SimpleNamespace(create_or_update=AsyncMock())
    session = SimpleNamespace(commit=AsyncMock())

    with pytest.raises(HTTPException) as err:
        await create_or_update_configuration(
            discord_guild_id="99",
            payload=_draft_payload(),
            guild_service=guild_service,
            configuration_service=configuration_service,
            bot_client=None,
            session=session,
        )

    assert err.value.status_code == 503
    assert err.value.detail["code"] == "guild_metadata_unavailable"
    configuration_service.create_or_update.assert_not_awaited()
    session.commit.assert_not_awaited()
