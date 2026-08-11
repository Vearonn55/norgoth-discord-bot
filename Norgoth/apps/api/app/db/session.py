"""Asynchronous SQLAlchemy engine and session management."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.db.url import require_database_url


@lru_cache(maxsize=4)
def _create_engine(
    database_url: str,
    *,
    echo: bool,
) -> AsyncEngine:
    """Create and cache an asynchronous SQLAlchemy engine."""

    return create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=4)
def _create_session_factory(
    database_url: str,
    *,
    echo: bool,
) -> async_sessionmaker[AsyncSession]:
    """Create and cache an asynchronous session factory."""

    engine = _create_engine(
        database_url,
        echo=echo,
    )

    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


def get_database_engine(
    settings: Settings | None = None,
) -> AsyncEngine:
    """Return the configured asynchronous SQLAlchemy engine."""

    resolved_settings = settings or get_settings()
    database_url = require_database_url(
        resolved_settings.database_url,
    )

    return _create_engine(
        database_url,
        echo=resolved_settings.database_echo,
    )


def get_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Return the configured asynchronous session factory."""

    resolved_settings = settings or get_settings()
    database_url = require_database_url(
        resolved_settings.database_url,
    )

    return _create_session_factory(
        database_url,
        echo=resolved_settings.database_echo,
    )


async def get_database_session() -> AsyncIterator[AsyncSession]:
    """Provide one database session for a FastAPI request."""

    session_factory = get_session_factory()

    async with session_factory() as session:
        yield session


async def dispose_database_engine(
    settings: Settings | None = None,
) -> None:
    """Dispose the configured engine when database configuration exists."""

    resolved_settings = settings or get_settings()

    if resolved_settings.database_url is None:
        return

    database_url = require_database_url(
        resolved_settings.database_url,
    )

    engine = _create_engine(
        database_url,
        echo=resolved_settings.database_echo,
    )

    await engine.dispose()
