"""Invite-code delta attribution (one-use, concurrent, vanity)."""

from __future__ import annotations

import sys
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.invites import resolve_invite_delta  # noqa: E402


def test_single_use_increase_is_attributed() -> None:
    assert resolve_invite_delta({"abc": 0}, {"abc": 1}) == ("abc", "attributed")


def test_vanity_increase() -> None:
    assert resolve_invite_delta({"vanity": 3}, {"vanity": 4}) == (
        "vanity",
        "vanity",
    )


def test_one_use_deleted_code_uses_tombstone_hint() -> None:
    assert resolve_invite_delta({"oneuse": 0}, {}) == ("oneuse", "deleted")


def test_concurrent_increases_are_ambiguous() -> None:
    assert resolve_invite_delta({"a": 1, "b": 2}, {"a": 2, "b": 3}) == (
        None,
        "ambiguous",
    )


def test_multiple_vanished_codes_are_ambiguous() -> None:
    assert resolve_invite_delta({"a": 0, "b": 0}, {}) == (None, "ambiguous")


def test_no_delta_is_unknown() -> None:
    assert resolve_invite_delta({"abc": 4}, {"abc": 4}) == (None, "unknown")
