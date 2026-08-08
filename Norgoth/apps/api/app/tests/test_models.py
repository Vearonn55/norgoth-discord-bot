"""Tests for Discord V1 SQLAlchemy model metadata."""

from typing import cast

import pytest
from sqlalchemy import Enum, Index, Table, UniqueConstraint
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import RelationshipProperty

from app.db.base import Base
from app.models import (
    BlacklistedGuild,
    Configuration,
    DiscordGuild,
    UserListEntry,
    VerificationLog,
)
from app.models.enums import UserListType, VerificationStatus
from app.models.types import DiscordSnowflake


def _get_table(model_table: object) -> Table:
    """Return a mapped model table with a precise static type."""

    return cast(Table, model_table)


def _unique_column_sets(table: Table) -> set[tuple[str, ...]]:
    """Return all unique-constraint column combinations."""

    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_column_sets(table: Table) -> set[tuple[str, ...]]:
    """Return all index column combinations."""

    return {
        tuple(column.name for column in index.columns)
        for index in table.indexes
        if isinstance(index, Index)
    }


def test_discord_v1_models_are_registered() -> None:
    """All Discord V1 models should be registered in shared metadata."""

    assert set(Base.metadata.tables) >= {
        "blacklisted_guilds",
        "configurations",
        "discord_guilds",
        "user_list_entries",
        "verification_logs",
    }


def test_discord_guild_has_expected_columns() -> None:
    """The Discord guild table should expose only approved V1 fields."""

    table = _get_table(DiscordGuild.__table__)

    assert set(table.columns.keys()) == {
        "id",
        "discord_guild_id",
        "discord_guild_name",
        "discord_owner_id",
        "created_at",
        "updated_at",
    }


def test_configuration_has_expected_columns() -> None:
    """The configuration table should expose approved V1 settings."""

    table = _get_table(Configuration.__table__)

    assert set(table.columns.keys()) == {
        "id",
        "guild_id",
        "verification_channel_id",
        "log_channel_id",
        "verified_role_id",
        "unverified_role_id",
        "member_role_id",
        "minimum_account_age_days",
        "session_timeout_seconds",
        "deny_vpn_or_proxy",
        "deny_shared_ip",
        "enabled",
        "created_at",
        "updated_at",
    }


def test_verification_log_has_expected_columns() -> None:
    """Verification logs should contain the approved security fields."""

    table = _get_table(VerificationLog.__table__)

    assert set(table.columns.keys()) == {
        "id",
        "guild_id",
        "discord_user_id",
        "status",
        "reason",
        "ip_hash",
        "ip_encrypted",
        "vpn_or_proxy_detected",
        "shared_ip_detected",
        "blacklisted_guild_detected",
        "created_at",
    }


def test_configuration_is_unique_per_guild() -> None:
    """Each Discord guild should have at most one configuration row."""

    table = _get_table(Configuration.__table__)

    assert ("guild_id",) in _unique_column_sets(table)


def test_discord_guild_id_is_globally_unique() -> None:
    """A Discord guild should be registered only once."""

    table = _get_table(DiscordGuild.__table__)

    assert ("discord_guild_id",) in _unique_column_sets(table)


def test_user_list_entry_is_unique_per_guild_and_user() -> None:
    """A user should have only one list entry per guild."""

    table = _get_table(UserListEntry.__table__)

    assert (
        "guild_id",
        "discord_user_id",
    ) in _unique_column_sets(table)


def test_blacklisted_guild_is_unique_per_owner_guild() -> None:
    """A target guild should be blacklisted only once per owner guild."""

    table = _get_table(BlacklistedGuild.__table__)

    assert (
        "guild_id",
        "blacklisted_discord_guild_id",
    ) in _unique_column_sets(table)


def test_owned_rows_cascade_when_guild_is_deleted() -> None:
    """Guild-owned rows should be deleted with their parent guild."""

    for model in (
        Configuration,
        VerificationLog,
        UserListEntry,
        BlacklistedGuild,
    ):
        table = _get_table(model.__table__)
        foreign_key = next(iter(table.c.guild_id.foreign_keys))

        assert foreign_key.ondelete == "CASCADE"


def test_configuration_relationship_is_one_to_one() -> None:
    """Discord guild configuration should be a one-to-one relationship."""

    relationship = cast(
        RelationshipProperty[object],
        DiscordGuild.__mapper__.relationships["configuration"],
    )

    assert relationship.uselist is False
    assert relationship.single_parent is True
    assert "delete-orphan" in relationship.cascade


def test_discord_identifiers_use_snowflake_type() -> None:
    """Every Discord identifier should use the shared snowflake type."""

    discord_guild_table = _get_table(DiscordGuild.__table__)
    configuration_table = _get_table(Configuration.__table__)
    verification_log_table = _get_table(VerificationLog.__table__)
    user_list_table = _get_table(UserListEntry.__table__)
    blacklisted_guild_table = _get_table(BlacklistedGuild.__table__)

    discord_columns = (
        discord_guild_table.c.discord_guild_id,
        discord_guild_table.c.discord_owner_id,
        configuration_table.c.verification_channel_id,
        configuration_table.c.log_channel_id,
        configuration_table.c.verified_role_id,
        configuration_table.c.unverified_role_id,
        configuration_table.c.member_role_id,
        verification_log_table.c.discord_user_id,
        user_list_table.c.discord_user_id,
        blacklisted_guild_table.c.blacklisted_discord_guild_id,
    )

    assert all(isinstance(column.type, DiscordSnowflake) for column in discord_columns)


def test_discord_snowflake_accepts_valid_value() -> None:
    """A valid Discord snowflake should pass bind validation."""

    snowflake_type = DiscordSnowflake()
    dialect = cast(Dialect, None)

    assert (
        snowflake_type.process_bind_param(
            "123456789012345678",
            dialect,
        )
        == "123456789012345678"
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        " ",
        "not-a-snowflake",
        "123 456",
        "-123",
        "123456789012345678901",
    ],
)
def test_discord_snowflake_rejects_invalid_values(
    invalid_value: str,
) -> None:
    """Malformed Discord identifiers should be rejected."""

    snowflake_type = DiscordSnowflake()
    dialect = cast(Dialect, None)

    with pytest.raises(
        ValueError,
        match="ASCII decimal digits",
    ):
        snowflake_type.process_bind_param(
            invalid_value,
            dialect,
        )


def test_verification_status_persists_lowercase_values() -> None:
    """Verification status values should remain stable and lowercase."""

    table = _get_table(VerificationLog.__table__)
    enum_type = cast(Enum, table.c.status.type)

    assert enum_type.enums == [
        VerificationStatus.SUCCESS.value,
        VerificationStatus.FAILED.value,
    ]


def test_user_list_type_persists_lowercase_values() -> None:
    """Whitelist and blacklist values should remain stable."""

    table = _get_table(UserListEntry.__table__)
    enum_type = cast(Enum, table.c.list_type.type)

    assert enum_type.enums == [
        UserListType.WHITELIST.value,
        UserListType.BLACKLIST.value,
    ]


def test_verification_log_has_required_lookup_indexes() -> None:
    """Verification logs should support common moderation lookups."""

    table = _get_table(VerificationLog.__table__)
    index_column_sets = _index_column_sets(table)

    assert ("guild_id",) in index_column_sets
    assert ("discord_user_id",) in index_column_sets
    assert ("ip_hash",) in index_column_sets


def test_encrypted_ip_is_binary_and_required() -> None:
    """Encrypted IP data should never be stored as plaintext text."""

    table = _get_table(VerificationLog.__table__)

    assert table.c.ip_encrypted.nullable is False
    assert table.c.ip_hash.nullable is False
    assert table.c.ip_encrypted.type.python_type is bytes
