"""Tests for embed message deployment-driven sync-status serialization."""

from types import SimpleNamespace
from typing import Any

from app.routes.embed_messages import _serialize


def _delivery(
    *,
    channel_id: str,
    status: str = "synced",
    deployed_version: int | None = 1,
    discord_message_id: str | None = "111",
    owner_feature: str = "embed_library",
    delivery_id: str | None = None,
) -> Any:
    return SimpleNamespace(
        id=delivery_id or f"d-{channel_id}",
        channel_id=channel_id,
        discord_message_id=discord_message_id,
        delivery_type="bot",
        status=status,
        error=None,
        deployed_version=deployed_version,
        owner_feature=owner_feature,
        last_synced_at=None,
        created_at=None,
    )


def _message(*, version: int, deliveries: list[Any]) -> Any:
    return SimpleNamespace(
        id="m-1",
        guild_id="g-1",
        name="Test",
        description="",
        content="",
        embed_json=None,
        version=version,
        created_by=None,
        created_at=None,
        updated_at=None,
        deliveries=deliveries,
    )


def test_no_deliveries_reports_draft_only() -> None:
    message = _message(version=1, deliveries=[])

    result = _serialize(message)

    assert result["sync_status"] == "draft_only"
    assert result["deployment_count"] == 0
    assert result["has_published"] is False


def test_all_current_reports_synced() -> None:
    message = _message(
        version=2,
        deliveries=[
            _delivery(channel_id="a", deployed_version=2),
            _delivery(channel_id="b", deployed_version=2),
        ],
    )

    result = _serialize(message)

    assert result["sync_status"] == "synced"
    assert result["synced_count"] == 2
    assert result["deployment_count"] == 2
    assert result["needs_resync"] is False


def test_live_but_stale_reports_out_of_date() -> None:
    message = _message(
        version=3,
        deliveries=[
            _delivery(channel_id="a", deployed_version=1),
            _delivery(channel_id="b", deployed_version=3),
        ],
    )

    result = _serialize(message)

    assert result["sync_status"] == "out_of_date"
    assert result["synced_count"] == 1
    assert result["needs_resync"] is True


def test_missing_message_library_reports_missing() -> None:
    message = _message(
        version=1,
        deliveries=[
            _delivery(channel_id="a", deployed_version=1),
            _delivery(
                channel_id="b",
                status="message_missing",
                discord_message_id=None,
            ),
        ],
    )

    result = _serialize(message)

    assert result["sync_status"] == "missing"
    assert result["needs_resync"] is True


def test_missing_message_sar_reports_needs_feature_repair() -> None:
    message = _message(
        version=1,
        deliveries=[
            _delivery(
                channel_id="b",
                status="message_missing",
                discord_message_id=None,
                owner_feature="self_assignable_role",
            ),
        ],
    )

    result = _serialize(message)

    assert result["sync_status"] == "needs_feature_repair"
    assert result["deliveries"][0]["state"] == "needs_feature_repair"


def test_runtime_binding_marks_sar_owner() -> None:
    message = _message(
        version=1,
        deliveries=[
            _delivery(
                channel_id="b",
                status="message_missing",
                discord_message_id=None,
                owner_feature="embed_library",
                delivery_id="bound-1",
            ),
        ],
    )

    # Even without the stored column, a runtime role-menu binding wins.
    result = _serialize(message, {"bound-1"})

    assert result["sync_status"] == "needs_feature_repair"


def test_error_delivery_reports_error() -> None:
    message = _message(
        version=1,
        deliveries=[
            _delivery(
                channel_id="a",
                status="permission_missing",
                discord_message_id=None,
            )
        ],
    )

    result = _serialize(message)

    assert result["sync_status"] == "error"
