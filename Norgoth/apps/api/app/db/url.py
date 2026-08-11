"""PostgreSQL database URL validation and normalization."""

POSTGRESQL_SCHEME = "postgresql://"
PSYCOPG_SCHEME = "postgresql+psycopg://"


class DatabaseConfigurationError(RuntimeError):
    """Raised when database configuration is missing or invalid."""


def normalize_database_url(database_url: str) -> str:
    """Normalize a PostgreSQL URL for SQLAlchemy's Psycopg dialect."""

    normalized_url = database_url.strip()

    if not normalized_url:
        message = "The configured database URL cannot be empty."
        raise DatabaseConfigurationError(message)

    if normalized_url.startswith(PSYCOPG_SCHEME):
        return normalized_url

    if normalized_url.startswith(POSTGRESQL_SCHEME):
        return normalized_url.replace(
            POSTGRESQL_SCHEME,
            PSYCOPG_SCHEME,
            1,
        )

    message = (
        "NORGOTH_DATABASE_URL must use either the "
        "'postgresql://' or 'postgresql+psycopg://' scheme."
    )
    raise DatabaseConfigurationError(message)


def require_database_url(database_url: str | None) -> str:
    """Return a valid database URL or raise a safe configuration error."""

    if database_url is None:
        message = "Database access was requested, but NORGOTH_DATABASE_URL is not configured."
        raise DatabaseConfigurationError(message)

    return normalize_database_url(database_url)
