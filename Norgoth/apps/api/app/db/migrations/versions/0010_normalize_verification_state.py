"""Normalize invalid Member Verification state.

The Member Verification master/detector tri-state is stored as
``(enabled, deny_vpn_or_proxy, deny_shared_ip)`` on ``guild_settings``. The only
invalid combination is master ON with both detectors OFF
(``enabled=true AND deny_vpn_or_proxy=false AND deny_shared_ip=false``): a
"verification on" state where nothing actually screens members. The new
backend state machine can never persist this, but a legacy row could exist.

This migration normalizes any such row to fully OFF (``enabled=false``). It is a
safe no-op for the common case (detectors default to true) and preserves
explicit admin choices. It intentionally does NOT re-derive the master from the
detectors for other rows, to avoid re-enabling verification for guilds that were
deliberately set to ``enabled=false``.

Revision ID: 0010_normalize_verif_state
Revises: 0009_detector_actions
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_normalize_verif_state"
down_revision: str | Sequence[str] | None = "0009_detector_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Normalize the invalid master-ON/both-detectors-OFF state to OFF."""

    op.execute(
        """
        UPDATE guild_settings
        SET enabled = false
        WHERE enabled = true
          AND deny_vpn_or_proxy = false
          AND deny_shared_ip = false
        """
    )


def downgrade() -> None:
    """No-op: the pre-normalization state was invalid and is not restorable."""
