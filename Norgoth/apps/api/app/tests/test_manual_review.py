"""Tests for the manual-review workflow: orchestration, roles, log, transcript.

These cover the post-Blacklisted-Guild behavior:

* the verification workflow captures the matched High Risk Server IDs and routes
  such members to manual review (no auto-reject);
* an approval grants Verified + Normal Member and removes Unverified, while a
  denial keeps the member Unverified;
* the atomic-claim resolution maps a lost race to ``None`` (409 upstream);
* the log-channel decision embed and transcript deep link are well-formed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.verification_logs import (
    _apply_review_roles,
    _build_transcript_url,
    _send_manual_review_decision,
)
from app.models.enums import RiskAction, UserListType, VerificationStatus
from app.services.verification_decision_service import (
    VerificationDecisionReason,
    VerificationDecisionService,
)
from app.services.verification_log_service import VerificationLogService
from app.services.verification_service import (
    VerificationRequest,
    VerificationService,
)


class _RecordingBotClient:
    """Fake DiscordBotClient recording role + message calls."""

    def __init__(self) -> None:
        self.added: list[tuple[str, str]] = []
        self.removed: list[tuple[str, str]] = []
        self.messages: list[tuple[str, dict]] = []

    async def add_member_role(self, *, guild_id, user_id, role_id, reason):
        self.added.append((role_id, reason))

    async def remove_member_role(self, *, guild_id, user_id, role_id, reason):
        self.removed.append((role_id, reason))

    async def send_channel_message(self, channel_id, payload):
        self.messages.append((channel_id, payload))


@pytest.mark.anyio
async def test_high_risk_membership_captures_ids_and_routes_manual_review() -> None:
    """High-risk membership triggers manual review + records matched IDs."""

    guild_id = uuid4()

    user_list_service = AsyncMock()
    user_list_service.get_entry.return_value = None

    high_risk_guild_service = AsyncMock()
    high_risk_guild_service.list_entries.return_value = [
        SimpleNamespace(high_risk_discord_guild_id="900000000000000001"),
        SimpleNamespace(high_risk_discord_guild_id="900000000000000002"),
    ]

    verification_log_service = AsyncMock()
    verification_log_service.has_shared_ip.return_value = False

    service = VerificationService(
        user_list_service=user_list_service,
        high_risk_guild_service=high_risk_guild_service,
        verification_log_service=verification_log_service,
        verification_decision_service=VerificationDecisionService(),
    )

    configuration = SimpleNamespace(
        minimum_account_age_days=7,
        deny_vpn_or_proxy=True,
        deny_shared_ip=True,
        vpn_or_proxy_action=RiskAction.DENY,
        shared_ip_action=RiskAction.DENY,
    )
    request = VerificationRequest(
        guild_id=guild_id,
        discord_user_id="123456789012345678",
        discord_user_guild_ids=frozenset(
            {"900000000000000002", "111111111111111111"}
        ),
        discord_account_age_days=365,
        ip_address="203.0.113.7",
        vpn_or_proxy_detected=False,
    )

    result = await service.verify(configuration=configuration, request=request)

    assert result.manual_review is True
    assert result.allowed is False
    assert result.reason is VerificationDecisionReason.HIGH_RISK_GUILD
    assert result.matched_high_risk_guild_ids == ("900000000000000002",)

    create_kwargs = verification_log_service.create_log.await_args.kwargs
    assert create_kwargs["status"] is VerificationStatus.MANUAL_REVIEW
    assert create_kwargs["matched_high_risk_guild_ids"] == ["900000000000000002"]


@pytest.mark.anyio
async def test_whitelisted_user_bypasses_high_risk() -> None:
    """A whitelisted user is allowed even when in a high-risk server."""

    user_list_service = AsyncMock()
    user_list_service.get_entry.return_value = SimpleNamespace(
        list_type=UserListType.WHITELIST
    )
    high_risk_guild_service = AsyncMock()
    high_risk_guild_service.list_entries.return_value = [
        SimpleNamespace(high_risk_discord_guild_id="900000000000000002"),
    ]
    verification_log_service = AsyncMock()
    verification_log_service.has_shared_ip.return_value = False

    service = VerificationService(
        user_list_service=user_list_service,
        high_risk_guild_service=high_risk_guild_service,
        verification_log_service=verification_log_service,
        verification_decision_service=VerificationDecisionService(),
    )

    result = await service.verify(
        configuration=SimpleNamespace(
            minimum_account_age_days=7,
            deny_vpn_or_proxy=True,
            deny_shared_ip=True,
            vpn_or_proxy_action=RiskAction.DENY,
            shared_ip_action=RiskAction.DENY,
        ),
        request=VerificationRequest(
            guild_id=uuid4(),
            discord_user_id="123456789012345678",
            discord_user_guild_ids=frozenset({"900000000000000002"}),
            discord_account_age_days=365,
            ip_address="203.0.113.7",
            vpn_or_proxy_detected=False,
        ),
    )

    assert result.allowed is True
    assert result.reason is VerificationDecisionReason.WHITELISTED


@pytest.mark.anyio
async def test_resolve_manual_review_atomic_claim_maps_lost_race_to_none() -> None:
    """When the atomic claim finds nothing to update, resolution is None."""

    repository = AsyncMock()
    repository.claim_manual_review.return_value = None

    service = VerificationLogService(repository, ip_protection_service=AsyncMock())

    result = await service.resolve_manual_review(
        guild_id=uuid4(),
        attempt_id=uuid4(),
        approved=True,
        reviewer_discord_id="42",
    )

    assert result is None
    repository.claim_manual_review.assert_awaited_once()


@pytest.mark.anyio
async def test_approve_grants_member_and_removes_unverified() -> None:
    """Approving a review grants the Base Member role and removes Unverified.

    The separate "verified" role was removed; verification converges on a
    two-role model (Unverified → Base Member).
    """

    bot = _RecordingBotClient()

    await _apply_review_roles(
        bot_client=bot,
        discord_guild_id="111111111111111111",
        discord_user_id="123456789012345678",
        approved=True,
        unverified_role_id="unverified-role",
        member_role_id="member-role",
    )

    added_roles = {role for role, _ in bot.added}
    removed_roles = {role for role, _ in bot.removed}
    assert added_roles == {"member-role"}
    assert removed_roles == {"unverified-role"}


@pytest.mark.anyio
async def test_deny_keeps_member_unverified() -> None:
    """Denying a review re-applies Unverified and grants nothing else."""

    bot = _RecordingBotClient()

    await _apply_review_roles(
        bot_client=bot,
        discord_guild_id="111111111111111111",
        discord_user_id="123456789012345678",
        approved=False,
        unverified_role_id="unverified-role",
        member_role_id="member-role",
    )

    assert bot.added == [("unverified-role", "Norgoth manual review rejected")]
    assert bot.removed == []


@pytest.mark.anyio
async def test_decision_log_embed_is_well_formed_with_transcript() -> None:
    """The decision embed posts once, disables mentions, and links the record."""

    bot = _RecordingBotClient()
    attempt_id = uuid4()

    await _send_manual_review_decision(
        bot_client=bot,
        log_channel_id="log-channel",
        discord_guild_id="111111111111111111",
        attempt_id=attempt_id,
        discord_user_id="123456789012345678",
        reviewer_discord_id="42",
        approved=True,
        transcript_url="https://dash.test/en/community/manual-verification/reviews/x?g=1",
    )

    assert len(bot.messages) == 1
    channel_id, payload = bot.messages[0]
    assert channel_id == "log-channel"
    assert payload["allowed_mentions"] == {"parse": []}
    embed = payload["embeds"][0]
    assert embed["title"] == "Manual Review Decision"
    field_names = {field["name"] for field in embed["fields"]}
    assert {"User", "Decision", "Reviewer", "Transcript"} <= field_names


def test_build_transcript_url_requires_dashboard_url() -> None:
    """Without a configured dashboard URL, no deep link is produced."""

    attempt_id = uuid4()

    assert (
        _build_transcript_url(
            dashboard_public_url=None,
            discord_guild_id="111111111111111111",
            attempt_id=attempt_id,
        )
        is None
    )

    url = _build_transcript_url(
        dashboard_public_url="https://dash.test/",
        discord_guild_id="111111111111111111",
        attempt_id=attempt_id,
    )
    assert url is not None
    assert url.endswith(
        f"/en/community/manual-verification/reviews/{attempt_id}"
        "?g=111111111111111111"
    )
