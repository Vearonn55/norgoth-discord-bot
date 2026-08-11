"""Tests for SQLAlchemy session infrastructure."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.db.session import (
    get_database_engine,
    get_session_factory,
)


def _create_database_settings() -> Settings:
    return Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment="testing",
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=("postgresql://user:password@localhost:5432/norgoth_test"),
        database_echo=False,
    )


def test_database_engine_can_be_created_without_connecting() -> None:
    """Engine construction should not establish a database connection."""

    engine = get_database_engine(_create_database_settings())

    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.database == "norgoth_test"


def test_session_factory_uses_async_sessions() -> None:
    """The session factory should create asynchronous sessions."""

    session_factory = get_session_factory(_create_database_settings())

    assert session_factory.class_ is AsyncSession
    assert session_factory.kw["autoflush"] is False
    assert session_factory.kw["expire_on_commit"] is False


def test_engine_configuration_is_cached() -> None:
    """Identical database settings should reuse the same engine."""

    settings = _create_database_settings()

    first_engine = get_database_engine(settings)
    second_engine = get_database_engine(settings)

    assert first_engine is second_engine
