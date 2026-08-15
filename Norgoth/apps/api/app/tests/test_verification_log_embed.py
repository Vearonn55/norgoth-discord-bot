"""Verification REST log title emojis and empty-field skip."""

from __future__ import annotations

import pytest

from app.api.v1.oauth import _send_verification_log_embed
from app.services.logging_presentation import (
    apply_log_title_emoji,
    filter_log_embed_fields,
)


def test_apply_log_title_emoji_prefixes_catalog_emoji() -> None:
    assert (
        apply_log_title_emoji("verification_succeeded", "Verification succeeded")
        == "✅ Verification succeeded"
    )
    assert (
        apply_log_title_emoji(
            "verification_succeeded_role_pending",
            "Verification succeeded — role pending",
        )
        == "✅ Verification succeeded — role pending"
    )
    assert (
        apply_log_title_emoji(
            "verification_manual_review_required",
            "Manual Review Required",
        )
        == "⚠️ Manual Review Required"
    )
    assert (
        apply_log_title_emoji("verification_denied", "Verification denied")
        == "❌ Verification denied"
    )
    assert (
        apply_log_title_emoji(
            "verification_manual_decision",
            "Manual Review Decision",
        )
        == "❌ Manual Review Decision"
    )


def test_apply_log_title_emoji_skips_double_prefix_and_unknown() -> None:
    assert apply_log_title_emoji("verification_denied", "❌ already") == "❌ already"
    assert apply_log_title_emoji("not_a_verification_event", "Plain") == "Plain"


def test_filter_log_embed_fields_drops_empty_unknown_and_dashes() -> None:
    kept = filter_log_embed_fields(
        [
            {"name": "User", "value": "<@1> (`1`)", "inline": False},
            {"name": "Display", "value": "—", "inline": True},
            {"name": "Empty", "value": "", "inline": True},
            {"name": "Unknown", "value": "#unknown", "inline": True},
            {"name": "Hyphen", "value": "-", "inline": True},
            {"name": "State", "value": "Allowed", "inline": True},
        ]
    )
    names = [field["name"] for field in kept]
    assert names == ["User", "State"]


@pytest.mark.asyncio
async def test_verification_log_embed_prefixes_emoji_and_skips_empty_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RecordingBot:
        def __init__(self) -> None:
            self.messages: list[tuple[str, dict]] = []

        async def send_channel_message(self, channel_id: str, payload: dict) -> None:
            self.messages.append((channel_id, payload))

    async def _fake_resolve(**_kwargs):
        return "log-channel", "logging_channels"

    monkeypatch.setattr(
        "app.api.v1.oauth.resolve_verification_log_channel",
        _fake_resolve,
    )

    bot = _RecordingBot()
    await _send_verification_log_embed(
        bot_client=bot,
        discord_guild_id="111111111111111111",
        legacy_log_channel_id="legacy",
        user_id="123456789012345678",
        username="",
        allowed=True,
        manual_review=False,
        reason="allowed",
        role_grant_failed=False,
        review_role_id="",
        vpn_or_proxy_detected=False,
        shared_ip_detected=False,
        high_risk_guild_detected=False,
    )

    assert len(bot.messages) == 1
    embed = bot.messages[0][1]["embeds"][0]
    assert embed["title"] == "✅ Verification succeeded"
    field_names = [field["name"] for field in embed["fields"]]
    assert "Display" not in field_names
    assert "User" in field_names
    assert "State" in field_names
