"""Production lifespan should not crash the API on optional encryption keys."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_application


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_name": "Norgoth Verification API",
        "app_version": "0.1.0",
        "environment": "production",
        "api_v1_prefix": "/api/v1",
        "log_level": "CRITICAL",
        "enable_docs": False,
        "database_url": None,
        "database_echo": False,
        "auth_enforced": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_production_startup_accepts_webhook_encryption_fallback() -> None:
    """Webhook encryption key is enough for production boot."""

    application = create_application(
        _production_settings(webhook_encryption_key=b"w" * 32)
    )

    with TestClient(application) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_production_startup_warns_when_encryption_keys_are_missing() -> None:
    """Missing encryption keys must not mark the API container unhealthy."""

    application = create_application(_production_settings())

    with TestClient(application) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_production_startup_rejects_enabled_docs() -> None:
    application = create_application(_production_settings(enable_docs=True))

    with pytest.raises(RuntimeError, match="NORGOTH_ENABLE_DOCS"):
        with TestClient(application):
            pass


def test_production_startup_rejects_unenforced_auth() -> None:
    application = create_application(_production_settings(auth_enforced=False))

    with pytest.raises(RuntimeError, match="NORGOTH_AUTH_ENFORCED"):
        with TestClient(application):
            pass
