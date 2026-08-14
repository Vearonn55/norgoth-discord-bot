"""Unit tests for log embed title emojis, field layout, and Discord limits."""

from __future__ import annotations

import sys
from pathlib import Path

import discord

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.logging_presentation import (  # noqa: E402
    apply_log_title_emoji,
    compose_log_embed_spec,
    compose_log_fields,
)
from bot.server_logging import build_log_embed  # noqa: E402


def test_apply_log_title_emoji_prefixes_known_events() -> None:
    assert apply_log_title_emoji("member_join", "Member joined") == "👋 Member joined"
    assert apply_log_title_emoji("member_ban", "Member banned") == "🔨 Member banned"
    assert apply_log_title_emoji("unknown_event", "Something happened") == (
        "Something happened"
    )


def test_apply_log_title_emoji_skips_existing_prefix() -> None:
    assert apply_log_title_emoji("ticket_opened", "🎫 Ticket opened") == (
        "🎫 Ticket opened"
    )
    assert apply_log_title_emoji("ticket_closed", "🔒 Ticket closed") == (
        "🔒 Ticket closed"
    )


def test_compose_log_fields_skips_empty_values() -> None:
    fields = compose_log_fields(
        {
            "Member": "Alice",
            "User ID": "123",
            "Reason": "",
            "Channel": "#unknown",
            "Before": "—",
        }
    )
    names = [name for name, _value, _inline in fields]
    assert names == ["Member", "User ID"]
    assert fields[0][2] is False
    assert fields[1][2] is True


def test_compose_log_fields_clamps_total_characters_by_dropping_ids_first() -> None:
    bulky = "x" * 1024
    fields = compose_log_fields(
        {
            "Member": bulky,
            "User ID": bulky,
            "Channel": bulky,
            "Channel ID": bulky,
            "Reason": bulky,
            "After": bulky,
            "Before": bulky,
        },
        title="👋 Member roles updated",
        description="Roles changed.",
        footer="NorBot · role event",
    )
    names = [name for name, _value, _inline in fields]
    assert "User ID" not in names
    assert "Channel ID" not in names
    total = (
        len("👋 Member roles updated")
        + len("Roles changed.")
        + len("NorBot · role event")
    )
    for name, value, _inline in fields:
        total += len(name) + len(value)
    assert total <= 6000
    assert len(fields) <= 20


def test_build_log_embed_uses_norbot_footer_and_emoji() -> None:
    embed = build_log_embed(
        "Member joined",
        "Alice joined the server.",
        color=discord.Color.green(),
        fields={"Member": "Alice", "User ID": "42", "Empty": ""},
        footer="NorBot · member event",
        event_type="member_join",
    )
    assert embed.title == "👋 Member joined"
    assert embed.description == "Alice joined the server."
    assert embed.footer.text == "NorBot · member event"
    assert [field.name for field in embed.fields] == ["Member", "User ID"]
    assert embed.fields[0].inline is False
    assert embed.fields[1].inline is True


def test_build_log_embed_unknown_event_has_no_emoji() -> None:
    embed = build_log_embed(
        "Custom event",
        "Details",
        color=discord.Color.blurple(),
        event_type="not_in_catalog",
    )
    assert embed.title == "Custom event"
