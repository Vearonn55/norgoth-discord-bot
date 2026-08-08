"""Tests for database URL configuration."""

import pytest

from app.db.url import (
    DatabaseConfigurationError,
    normalize_database_url,
    require_database_url,
)


def test_postgresql_url_is_normalized_for_psycopg() -> None:
    """Standard PostgreSQL URLs should use SQLAlchemy's Psycopg dialect."""

    result = normalize_database_url(
        "postgresql://user:password@localhost:5432/norgoth",
    )

    assert result == ("postgresql+psycopg://user:password@localhost:5432/norgoth")


def test_psycopg_url_is_preserved() -> None:
    """An existing Psycopg SQLAlchemy URL should remain unchanged."""

    database_url = "postgresql+psycopg://user:password@localhost:5432/norgoth"

    assert normalize_database_url(database_url) == database_url


def test_database_url_surrounding_whitespace_is_removed() -> None:
    """Database URLs should be normalized after trimming whitespace."""

    result = normalize_database_url(
        "  postgresql://user:password@localhost:5432/norgoth  ",
    )

    assert result == ("postgresql+psycopg://user:password@localhost:5432/norgoth")


def test_missing_database_url_raises_safe_error() -> None:
    """Database access should fail clearly when no URL is configured."""

    with pytest.raises(
        DatabaseConfigurationError,
        match="NORGOTH_DATABASE_URL is not configured",
    ):
        require_database_url(None)


def test_empty_database_url_is_rejected() -> None:
    """Empty database URLs should be rejected."""

    with pytest.raises(
        DatabaseConfigurationError,
        match="cannot be empty",
    ):
        normalize_database_url("   ")


def test_unsupported_database_scheme_is_rejected() -> None:
    """Non-PostgreSQL database schemes should be rejected."""

    with pytest.raises(
        DatabaseConfigurationError,
        match="must use either",
    ):
        normalize_database_url("sqlite:///norgoth.db")
