"""Configurable risk-detector actions for VPN/Proxy and Shared IP.

Adds ``guild_settings.vpn_or_proxy_action`` and ``guild_settings.shared_ip_action``
so each detector's outcome (deny vs. manual review) is configurable per guild.

Existing guilds default to ``deny`` (via ``server_default``), preserving the
current hard-deny behavior so verification security does not silently weaken.
The existing ``deny_vpn_or_proxy`` / ``deny_shared_ip`` booleans are reused as
the detector ENABLED flags.

Revision ID: 0009_detector_actions
Revises: 0008_high_risk_manual_review
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_detector_actions"
down_revision: str | Sequence[str] | None = "0008_high_risk_manual_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED = "('deny', 'manual_review')"


def upgrade() -> None:
    """Apply this migration."""

    op.add_column(
        "guild_settings",
        sa.Column(
            "vpn_or_proxy_action",
            sa.String(length=16),
            nullable=False,
            server_default="deny",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "shared_ip_action",
            sa.String(length=16),
            nullable=False,
            server_default="deny",
        ),
    )

    op.create_check_constraint(
        "vpn_or_proxy_action",
        "guild_settings",
        f"vpn_or_proxy_action IN {_ALLOWED}",
    )
    op.create_check_constraint(
        "shared_ip_action",
        "guild_settings",
        f"shared_ip_action IN {_ALLOWED}",
    )


def downgrade() -> None:
    """Revert this migration."""

    op.drop_constraint(
        op.f("ck_guild_settings_shared_ip_action"),
        "guild_settings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_guild_settings_vpn_or_proxy_action"),
        "guild_settings",
        type_="check",
    )
    op.drop_column("guild_settings", "shared_ip_action")
    op.drop_column("guild_settings", "vpn_or_proxy_action")
