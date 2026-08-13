"""Unit tests for verification log channel routing helpers."""

from __future__ import annotations

from app.services.verification_log_routing import classification_to_event_type


def test_classification_to_event_type() -> None:
    assert (
        classification_to_event_type(
            allowed=True, manual_review=False, role_grant_failed=False
        )
        == "verification_succeeded"
    )
    assert (
        classification_to_event_type(
            allowed=True, manual_review=False, role_grant_failed=True
        )
        == "verification_succeeded_role_pending"
    )
    assert (
        classification_to_event_type(
            allowed=False, manual_review=True, role_grant_failed=False
        )
        == "verification_manual_review_required"
    )
    assert (
        classification_to_event_type(
            allowed=False, manual_review=False, role_grant_failed=False
        )
        == "verification_denied"
    )
