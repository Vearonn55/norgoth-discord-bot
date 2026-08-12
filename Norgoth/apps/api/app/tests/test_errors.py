"""Tests for standardized application exception responses."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.main import create_application


class ValidationPayload(BaseModel):
    """Payload used to verify request-validation behavior."""

    count: int


def _create_test_settings() -> Settings:
    return Settings(
        app_name="Norgoth Verification API",
        app_version="0.1.0",
        environment="testing",
        api_v1_prefix="/api/v1",
        log_level="CRITICAL",
        enable_docs=False,
        database_url=None,
        database_echo=False,
    )


def _create_validation_test_application() -> FastAPI:
    application = create_application(_create_test_settings())

    @application.post("/test/validation")
    async def validate_payload(
        payload: ValidationPayload,
    ) -> ValidationPayload:
        return payload

    return application


def _create_failure_test_application() -> FastAPI:
    application = create_application(_create_test_settings())

    @application.get("/test/failure")
    async def raise_unexpected_error() -> None:
        message = "Internal implementation detail"
        raise RuntimeError(message)

    return application


def test_validation_error_returns_standardized_response() -> None:
    """Invalid request bodies should use the standard error envelope."""

    application = _create_validation_test_application()

    with TestClient(application) as client:
        response = client.post(
            "/test/validation",
            json={"count": "not-an-integer"},
            headers={"X-Request-ID": "validation-request-001"},
        )

    response_body = response.json()

    assert response.status_code == 422
    assert response_body["error"]["code"] == "request_validation_failed"
    assert response_body["error"]["message"] == ("The request did not pass validation.")
    assert response_body["error"]["request_id"] == "validation-request-001"
    assert len(response_body["error"]["validation_issues"]) == 1
    assert response_body["error"]["validation_issues"][0]["location"] == [
        "body",
        "count",
    ]


def test_structured_http_exception_preserves_error_code() -> None:
    """HTTPException detail dicts should surface as error.code."""

    application = create_application(_create_test_settings())

    @application.get("/test/structured")
    async def raise_structured() -> None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "discord_token_invalid",
                "message": "Please reconnect Discord.",
            },
        )

    with TestClient(application) as client:
        response = client.get(
            "/test/structured",
            headers={"X-Request-ID": "structured-request-001"},
        )

    body = response.json()
    assert response.status_code == 401
    assert body["error"]["code"] == "discord_token_invalid"
    assert body["error"]["message"] == "Please reconnect Discord."
    assert body["error"]["request_id"] == "structured-request-001"


def test_unexpected_error_does_not_expose_internal_details() -> None:
    """Unexpected errors should not leak exception details."""

    application = _create_failure_test_application()

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/test/failure",
            headers={"X-Request-ID": "failure-request-001"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected server error occurred.",
            "request_id": "failure-request-001",
        },
    }
    assert "Internal implementation detail" not in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
