"""Tests for configurable risk-detector settings and related regressions."""

from typing import Any

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.models.enums import RiskAction
from app.models.guild_high_risk_guild import GuildHighRiskGuild
from app.models.guild_settings import GuildSettings
from app.schemas.configuration import (
    ConfigurationUpsertRequest,
    DetectorConfigPatchRequest,
)


def _registered_operations() -> set[tuple[str, str]]:
    """Return paths and methods exposed by the V1 API router."""

    application = FastAPI()
    application.include_router(api_router)

    schema: dict[str, Any] = application.openapi()
    paths: dict[str, Any] = schema["paths"]

    return {
        (path, method.upper())
        for path, operations in paths.items()
        for method in operations
        if method.lower() in {"get", "put", "post", "patch", "delete"}
    }


def test_router_exposes_detectors_patch_route() -> None:
    """The detectors PATCH endpoint should be registered."""

    operations = _registered_operations()

    assert (
        "/guilds/{discord_guild_id}/configuration/detectors",
        "PATCH",
    ) in operations


def test_detector_patch_request_defaults_to_none() -> None:
    """An empty detector patch leaves every field unset (no accidental writes)."""

    payload = DetectorConfigPatchRequest()

    assert payload.deny_vpn_or_proxy is None
    assert payload.vpn_or_proxy_action is None
    assert payload.deny_shared_ip is None
    assert payload.shared_ip_action is None


def test_detector_patch_request_accepts_actions() -> None:
    """Action values should validate against the RiskAction enum."""

    payload = DetectorConfigPatchRequest(
        vpn_or_proxy_action=RiskAction.MANUAL_REVIEW,
        shared_ip_action=RiskAction.DENY,
    )

    assert payload.vpn_or_proxy_action is RiskAction.MANUAL_REVIEW
    assert payload.shared_ip_action is RiskAction.DENY


def test_configuration_upsert_defaults_actions_to_deny() -> None:
    """New/updated configs default both detector actions to DENY.

    This preserves the legacy hard-deny behavior when a client omits the
    action fields, matching the migration's server_default.
    """

    payload = ConfigurationUpsertRequest(
        verification_channel_id="1",
        log_channel_id="2",
        verified_role_id="3",
        unverified_role_id="4",
        member_role_id="5",
    )

    assert payload.vpn_or_proxy_action is RiskAction.DENY
    assert payload.shared_ip_action is RiskAction.DENY


def test_guild_settings_defines_detector_action_columns() -> None:
    """GuildSettings must carry the two persisted risk-action columns."""

    columns = set(GuildSettings.__table__.columns.keys())

    assert "vpn_or_proxy_action" in columns
    assert "shared_ip_action" in columns


def test_high_risk_guild_table_name_is_stable() -> None:
    """Regression: the High-Risk table must keep its expected name.

    The High-Risk Servers tab 500'd when the ``guild_high_risk_guilds`` table
    was missing (migrations 0007/0008 unapplied). Guard the table name so a
    rename cannot silently reintroduce the failure.
    """

    assert GuildHighRiskGuild.__tablename__ == "guild_high_risk_guilds"
