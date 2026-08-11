"""Unit tests for invite logging mapping auto-heal."""

from __future__ import annotations

from app.models.logging_config import LoggingChannel, LoggingConfiguration
from app.routes.logging_config import (
    INVITE_LOG_EVENTS,
    _heal_invite_event_mappings,
    _pick_invite_log_channel,
)


def test_pick_invite_log_channel_prefers_invites_key() -> None:
    config = LoggingConfiguration(guild_id="1", status="active", enabled=True)
    member = LoggingChannel(
        guild_id="1", key="member", name="member-log", channel_id="111"
    )
    invites = LoggingChannel(
        guild_id="1", key="invites", name="invites-log", channel_id="222"
    )
    config.channels.extend([member, invites])
    assert _pick_invite_log_channel(config) is invites


def test_heal_invite_event_mappings_adds_missing_once() -> None:
    config = LoggingConfiguration(guild_id="1535194176197500940", status="active")
    config.enabled = True
    channel = LoggingChannel(
        guild_id=config.guild_id,
        key="member",
        name="member-log",
        channel_id="1536043762986393780",
    )
    config.channels.append(channel)

    assert _heal_invite_event_mappings(config) is True
    types = {mapping.event_type for mapping in config.event_mappings}
    assert types == set(INVITE_LOG_EVENTS)
    assert all(mapping.enabled for mapping in config.event_mappings)
    assert all(mapping.channel is channel for mapping in config.event_mappings)

    assert _heal_invite_event_mappings(config) is False


def test_heal_invite_event_mappings_skips_without_provisioned_channel() -> None:
    config = LoggingConfiguration(guild_id="1", status="active")
    config.channels.append(
        LoggingChannel(guild_id="1", key="invites", name="invites-log", channel_id=None)
    )
    assert _heal_invite_event_mappings(config) is False
    assert config.event_mappings == []


def test_heal_invite_event_mappings_skips_draft() -> None:
    config = LoggingConfiguration(guild_id="1", status="draft")
    config.channels.append(
        LoggingChannel(guild_id="1", key="invites", name="invites-log", channel_id="1")
    )
    assert _heal_invite_event_mappings(config) is False
