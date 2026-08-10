"""Tests for the Member Verification master/detector state machine."""

from typing import Any

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.schemas.configuration import VerificationStatePatchRequest
from app.services.configuration_service import (
    normalize_verification_state,
    resolve_verification_state,
)


def _registered_operations() -> set[tuple[str, str]]:
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


def test_router_exposes_state_patch_route() -> None:
    """The verification state PATCH endpoint should be registered."""

    assert (
        "/guilds/{discord_guild_id}/configuration/state",
        "PATCH",
    ) in _registered_operations()


def test_state_patch_request_defaults_to_none() -> None:
    payload = VerificationStatePatchRequest()

    assert payload.enabled is None
    assert payload.deny_vpn_or_proxy is None
    assert payload.deny_shared_ip is None


def test_normalize_rejects_master_on_both_detectors_off() -> None:
    assert normalize_verification_state(True, False, False) == (False, False, False)


def test_normalize_preserves_valid_states() -> None:
    assert normalize_verification_state(True, True, True) == (True, True, True)
    assert normalize_verification_state(True, True, False) == (True, True, False)
    assert normalize_verification_state(True, False, True) == (True, False, True)
    assert normalize_verification_state(False, False, False) == (False, False, False)


def test_master_on_forces_both_detectors() -> None:
    assert resolve_verification_state((False, False, False), enabled=True) == (
        True,
        True,
        True,
    )


def test_master_off_forces_both_detectors_off() -> None:
    assert resolve_verification_state((True, True, True), enabled=False) == (
        False,
        False,
        False,
    )


def test_turning_off_one_detector_keeps_master_on() -> None:
    assert resolve_verification_state(
        (True, True, True), deny_vpn_or_proxy=False
    ) == (True, False, True)
    assert resolve_verification_state(
        (True, True, True), deny_shared_ip=False
    ) == (True, True, False)


def test_turning_off_last_detector_auto_disables_master() -> None:
    # From ON_shared (T/F/T), turning shared off leaves no detector -> master OFF.
    assert resolve_verification_state(
        (True, False, True), deny_shared_ip=False
    ) == (False, False, False)
    # From ON_vpn (T/T/F), turning vpn off -> master OFF.
    assert resolve_verification_state(
        (True, True, False), deny_vpn_or_proxy=False
    ) == (False, False, False)


def test_turning_a_detector_on_re_enables_master() -> None:
    assert resolve_verification_state(
        (False, False, False), deny_vpn_or_proxy=True
    ) == (True, True, False)
