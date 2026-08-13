"""Regression: create-on-demand verification state must refresh timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import RiskAction
from app.models.guild_settings import GuildSettings
from app.schemas.configuration import ConfigurationResponse
from app.services.configuration_service import ConfigurationService
from app.services.views import ConfigurationView


def test_configuration_response_rejects_null_timestamps() -> None:
    """Reproduces the enable-500 root cause: missing server-default datetimes."""

    with pytest.raises(ValidationError):
        ConfigurationResponse.model_validate(
            {
                "id": uuid4(),
                "guild_id": uuid4(),
                "verification_channel_id": "",
                "log_channel_id": "",
                "unverified_role_id": "",
                "member_role_id": "",
                "manual_review_role_id": "",
                "minimum_account_age_days": 0,
                "session_timeout_seconds": 900,
                "deny_vpn_or_proxy": True,
                "deny_shared_ip": True,
                "vpn_or_proxy_action": RiskAction.DENY,
                "shared_ip_action": RiskAction.DENY,
                "enabled": True,
                "created_at": None,
                "updated_at": None,
            }
        )


@pytest.mark.asyncio
async def test_apply_verification_state_refreshes_after_create() -> None:
    """First enable must refresh ORM so server_default timestamps populate."""

    guild_id = uuid4()
    now = datetime.now(timezone.utc)

    repo = AsyncMock()
    repo.get_settings = AsyncMock(return_value=None)
    repo.flush = AsyncMock()
    repo.get_role_bindings = AsyncMock(return_value={})
    repo.get_channel_bindings = AsyncMock(return_value={})

    async def _refresh(instance: object) -> None:
        assert isinstance(instance, GuildSettings)
        if instance.id is None:
            instance.id = uuid4()
        if instance.minimum_account_age_days is None:
            instance.minimum_account_age_days = 0
        if instance.session_timeout_seconds is None:
            instance.session_timeout_seconds = 900
        if instance.vpn_or_proxy_action is None:
            instance.vpn_or_proxy_action = RiskAction.DENY
        if instance.shared_ip_action is None:
            instance.shared_ip_action = RiskAction.DENY
        instance.created_at = now
        instance.updated_at = now

    repo.refresh = AsyncMock(side_effect=_refresh)
    repo.add = AsyncMock()

    service = ConfigurationService(repo)
    view = await service.apply_verification_state(guild_id=guild_id, enabled=True)

    repo.add.assert_awaited()
    repo.flush.assert_awaited()
    repo.refresh.assert_awaited()
    assert isinstance(view, ConfigurationView)
    assert view.enabled is True
    assert view.deny_vpn_or_proxy is True
    assert view.deny_shared_ip is True
    assert view.created_at == now
    assert view.updated_at == now
    ConfigurationResponse.model_validate(view)
