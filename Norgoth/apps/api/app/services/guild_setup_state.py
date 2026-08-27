"""Derive selector setup_state from bot guild membership presence."""

from __future__ import annotations

SetupState = str


def derive_setup_state(*, bot_installed: bool) -> SetupState:
    """Map NorBot guild membership to a binary selector state."""

    if bot_installed:
        return "installed"
    return "not_installed"
