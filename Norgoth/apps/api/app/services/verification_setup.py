"""Derive Member Verification setup readiness from durable configuration."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.views import ConfigurationView

REQUIRED_BINDING_FIELDS: tuple[str, ...] = (
    "verification_channel_id",
    "unverified_role_id",
    "member_role_id",
)

VerificationSetupState = str


@dataclass(frozen=True, slots=True)
class VerificationSetupStatus:
    """Derived readiness for authorize and dashboard UX."""

    state: VerificationSetupState
    missing: tuple[str, ...]
    code: str


def missing_required_bindings(
    configuration: ConfigurationView | None,
) -> tuple[str, ...]:
    """Return required binding field names that are empty."""

    if configuration is None:
        return REQUIRED_BINDING_FIELDS
    missing: list[str] = []
    for field in REQUIRED_BINDING_FIELDS:
        value = getattr(configuration, field, "") or ""
        if not str(value).strip():
            missing.append(field)
    return tuple(missing)


def derive_verification_setup_state(
    configuration: ConfigurationView | None,
    *,
    degraded: bool = False,
    error: bool = False,
) -> VerificationSetupStatus:
    """Map settings + bindings to a public/admin setup state."""

    if configuration is None:
        return VerificationSetupStatus(
            state="not_configured",
            missing=REQUIRED_BINDING_FIELDS,
            code="verification_not_configured",
        )

    missing = missing_required_bindings(configuration)
    if missing:
        return VerificationSetupStatus(
            state="incomplete",
            missing=missing,
            code="verification_setup_incomplete",
        )

    if error:
        return VerificationSetupStatus(
            state="error",
            missing=(),
            code="guild_metadata_unavailable",
        )

    if degraded:
        return VerificationSetupStatus(
            state="degraded",
            missing=(),
            code="discord_resource_not_in_guild",
        )

    if not configuration.enabled:
        return VerificationSetupStatus(
            state="disabled",
            missing=(),
            code="verification_disabled",
        )

    return VerificationSetupStatus(
        state="active",
        missing=(),
        code="verification_active",
    )


def has_required_bindings(configuration: ConfigurationView | None) -> bool:
    return configuration is not None and not missing_required_bindings(configuration)
