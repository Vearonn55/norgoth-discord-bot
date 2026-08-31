"""Tests that verification OAuth callback commits durable attempt rows."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1 import oauth as oauth_module
from app.api.v1.oauth import ProxycheckSignals
from app.models.enums import RiskAction
from app.services.verification_decision_service import VerificationDecisionReason
from app.services.verification_service import VerificationResult
from app.services.verification_guild_membership import HighRiskMembershipResult
from app.services.views import ConfigurationView


def _active_configuration() -> ConfigurationView:
    return ConfigurationView(
        id=uuid4(),
        guild_id=uuid4(),
        verification_channel_id="111",
        log_channel_id="222",
        unverified_role_id="333",
        member_role_id="444",
        manual_review_role_id="",
        minimum_account_age_days=7,
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


@pytest.mark.anyio
async def test_discord_callback_commits_after_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful verify must commit before Discord side effects."""

    session = AsyncMock()
    session.commit = AsyncMock()
    attempt_id = uuid4()

    verification_result = VerificationResult(
        allowed=False,
        manual_review=True,
        reason=VerificationDecisionReason.HIGH_RISK_GUILD,
        shared_ip_detected=False,
        high_risk_guild_detected=True,
        matched_high_risk_guild_ids=("900000000000000001",),
        banned_ip_match_detected=False,
        matched_banned_user_ids=(),
        review_evidence=None,
        attempt_id=attempt_id,
    )
    verification_service = AsyncMock()
    verification_service.verify = AsyncMock(return_value=verification_result)

    request = SimpleNamespace(
        headers={"accept-language": "en"},
        client=SimpleNamespace(host="127.0.0.1"),
        state=SimpleNamespace(request_id="req-test"),
        query_params={},
    )

    configuration = _active_configuration()
    guild = SimpleNamespace(
        id=configuration.guild_id,
        discord_guild_id="111111111111111111",
        discord_guild_name="Test Guild",
    )
    user = SimpleNamespace(id="123456789012345678", global_name="Test", username="tester")
    verified_state = SimpleNamespace(
        discord_guild_id="111111111111111111",
        lang="en",
        purpose="verification",
        nonce="nonce",
    )

    monkeypatch.setattr(oauth_module, "_get_client_ip", lambda _request: "203.0.113.1")
    monkeypatch.setattr(
        oauth_module,
        "enforce_verification_rate_limit",
        AsyncMock(),
    )
    monkeypatch.setattr(
        oauth_module,
        "consume_oauth_nonce",
        AsyncMock(),
    )
    monkeypatch.setattr(
        oauth_module,
        "_proxycheck_vpn_or_proxy_detected",
        AsyncMock(
            return_value=ProxycheckSignals(
                vpn_or_proxy_detected=False,
                risk_provider_unavailable=False,
                proxy_classification=None,
            )
        ),
    )
    monkeypatch.setattr(
        oauth_module,
        "resolve_guild_public_meta",
        AsyncMock(
            return_value=SimpleNamespace(name="Test Guild", icon_url=None),
        ),
    )
    monkeypatch.setattr(
        oauth_module,
        "_build_display_context_token",
        lambda **_kwargs: "ctx-token",
    )
    monkeypatch.setattr(
        oauth_module,
        "_apply_verification_roles",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        oauth_module,
        "_send_verification_log_embed",
        AsyncMock(),
    )
    monkeypatch.setattr(
        oauth_module,
        "_verify_result_redirect",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=303),
    )
    monkeypatch.setattr(
        oauth_module,
        "resolve_high_risk_membership",
        AsyncMock(
            return_value=HighRiskMembershipResult(
                matched_high_risk_guild_ids=("900000000000000001",),
                membership_check_unavailable=False,
            )
        ),
    )

    oauth_state_service = SimpleNamespace(verify=lambda _state: verified_state)
    oauth_client = SimpleNamespace(
        exchange_code=AsyncMock(
            return_value=SimpleNamespace(
                access_token="token",
                scope=frozenset({"identify", "guilds"}),
            )
        ),
        get_current_user=AsyncMock(return_value=user),
    )
    guild_service = SimpleNamespace(
        get_by_discord_guild_id=AsyncMock(return_value=guild),
    )
    configuration_service = SimpleNamespace(
        get_by_guild_id=AsyncMock(return_value=configuration),
    )
    verification_log_service = SimpleNamespace(
        get_open_manual_review_for_user=AsyncMock(return_value=None),
    )
    high_risk_guild_service = SimpleNamespace(list_entries=AsyncMock(return_value=[]))
    bot_client = SimpleNamespace(get_guild_member=AsyncMock(return_value={"roles": []}))
    settings = SimpleNamespace(dashboard_public_url="https://www.norbot.io")

    await oauth_module.discord_callback(
        request=request,
        session=session,
        oauth_client=oauth_client,
        oauth_state_service=oauth_state_service,
        guild_service=guild_service,
        configuration_service=configuration_service,
        proxycheck_client=AsyncMock(),
        verification_service=verification_service,
        verification_log_service=verification_log_service,
        high_risk_guild_service=high_risk_guild_service,
        bot_client=bot_client,
        settings=settings,
        code="oauth-code",
        state_value="signed-state",
        error=None,
    )

    verification_service.verify.assert_awaited_once()
    session.commit.assert_awaited_once()
