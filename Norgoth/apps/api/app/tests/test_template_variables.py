"""Tests for campaign {user_name} resolution policy."""

from __future__ import annotations

from app.services.template_variables import (
    USER_NAME_FALLBACK,
    resolve_user_name,
    resolve_user_name_from_recipient,
)
from app.workers.campaign_worker import render_campaign_text


def test_resolve_user_name_prefers_display_name() -> None:
    assert (
        resolve_user_name(display_name="Alice", name="alice_user") == "Alice"
    )


def test_resolve_user_name_falls_back_to_name() -> None:
    assert resolve_user_name(display_name=None, name="alice_user") == "alice_user"


def test_resolve_user_name_uses_neutral_fallback() -> None:
    assert resolve_user_name() == USER_NAME_FALLBACK
    assert USER_NAME_FALLBACK == "member"


def test_resolve_from_recipient_dict() -> None:
    assert (
        resolve_user_name_from_recipient(
            {"display_name": "Bob", "name": "bob"}
        )
        == "Bob"
    )
    assert resolve_user_name_from_recipient({"name": "bob"}) == "bob"
    assert resolve_user_name_from_recipient({}) == "member"
    assert resolve_user_name_from_recipient(None) == "member"


def test_render_campaign_text_substitutes_user_name() -> None:
    text = render_campaign_text(
        "Hello {user_name} from {server_name} — {campaign_name}",
        user_name="member",
        server_name="Norgoth",
        campaign_name="Launch",
    )
    assert text == "Hello member from Norgoth — Launch"
    assert "there" not in text
