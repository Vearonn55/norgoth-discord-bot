"""Auto Moderation PUT validation: snowflakes, empty enable, channel conflicts."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routes.automod import (
    AutomodConfig,
    sanitize_automod_id_lists,
    snowflake_list,
    validate_format_channel_rules,
)


def test_snowflake_list_strips_invalid_and_dedupes() -> None:
    assert snowflake_list(
        ["111111111111111111", "not-an-id", "111111111111111111", "22", "abc"]
    ) == ["111111111111111111"]
    assert snowflake_list(["222222222222222222", "333333333333333333"]) == [
        "222222222222222222",
        "333333333333333333",
    ]


def test_sanitize_id_lists_covers_exempt_and_format_channels() -> None:
    payload = sanitize_automod_id_lists(
        {
            "exempt_channel_ids": ["111111111111111111", "nope"],
            "exempt_role_ids": ["222222222222222222"],
            "image_only_channel_ids": ["333333333333333333", "333333333333333333"],
            "link_only_channel_ids": ["javascript:alert(1)"],
        }
    )
    assert payload["exempt_channel_ids"] == ["111111111111111111"]
    assert payload["exempt_role_ids"] == ["222222222222222222"]
    assert payload["image_only_channel_ids"] == ["333333333333333333"]
    assert payload["link_only_channel_ids"] == []


def test_enabled_image_only_without_channels_is_400() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_format_channel_rules(
            {"image_only_enabled": True, "image_only_channel_ids": []}
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "automod_image_only_channels_required"


def test_enabled_link_only_without_channels_is_400() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_format_channel_rules(
            {"link_only_enabled": True, "link_only_channel_ids": []}
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "automod_link_only_channels_required"


def test_overlapping_format_channels_is_409() -> None:
    channel = "111111111111111111"
    with pytest.raises(HTTPException) as exc:
        validate_format_channel_rules(
            {
                "image_only_enabled": True,
                "link_only_enabled": True,
                "image_only_channel_ids": [channel, "222222222222222222"],
                "link_only_channel_ids": [channel],
            }
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "automod_channel_rule_conflict"
    assert exc.value.detail["channel_ids"] == [channel]


def test_disabled_rules_may_keep_empty_channel_lists() -> None:
    validate_format_channel_rules(
        {
            "image_only_enabled": False,
            "link_only_enabled": False,
            "image_only_channel_ids": [],
            "link_only_channel_ids": [],
        }
    )


def test_pydantic_defaults_disable_format_rules() -> None:
    config = AutomodConfig()
    dumped = config.model_dump()
    assert dumped["image_only_enabled"] is False
    assert dumped["link_only_enabled"] is False
    assert dumped["image_only_channel_ids"] == []
    assert dumped["link_only_channel_ids"] == []
    assert dumped["image_only_action"] == "delete"
    assert dumped["link_only_action"] == "delete"


def test_unknown_stored_keys_are_dropped_on_model_validate() -> None:
    config = AutomodConfig.model_validate(
        {
            "enabled": True,
            "legacy_flag": True,
            "image_only_enabled": True,
            "image_only_channel_ids": ["111111111111111111"],
        }
    )
    dumped = config.model_dump()
    assert "legacy_flag" not in dumped
    assert dumped["enabled"] is True
    assert dumped["image_only_enabled"] is True
    assert dumped["image_only_channel_ids"] == ["111111111111111111"]
