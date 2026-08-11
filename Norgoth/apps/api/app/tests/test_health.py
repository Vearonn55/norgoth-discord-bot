"""Tests for the API liveness endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_application_status() -> None:
    """The liveness endpoint should return stable application metadata."""

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Norgoth Verification API",
        "version": "0.1.0",
        "environment": "development",
    }


def test_health_endpoint_returns_request_and_security_headers() -> None:
    """Successful responses should include standard API headers."""

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    request_id = response.headers["X-Request-ID"]

    assert len(request_id) >= 8
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == ("camera=(), geolocation=(), microphone=()")


def test_valid_caller_request_id_is_preserved() -> None:
    """A safe caller-provided request ID should be returned unchanged."""

    request_id = "norgoth-test-request-001"

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": request_id},
        )

    assert response.headers["X-Request-ID"] == request_id


def test_invalid_caller_request_id_is_replaced() -> None:
    """An unsafe request ID should not be reflected to the caller."""

    invalid_request_id = "invalid request id with spaces"

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": invalid_request_id},
        )

    generated_request_id = response.headers["X-Request-ID"]

    assert generated_request_id != invalid_request_id
    assert len(generated_request_id) >= 8


def test_unknown_endpoint_returns_standardized_error() -> None:
    """Unknown routes should return the standard API error envelope."""

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/does-not-exist",
            headers={"X-Request-ID": "not-found-request-001"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": "not-found-request-001",
        },
    }
    assert response.headers["X-Request-ID"] == "not-found-request-001"


def test_unsupported_method_returns_standardized_error() -> None:
    """Unsupported methods should return the standard API error envelope."""

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/health",
            headers={"X-Request-ID": "method-request-001"},
        )

    assert response.status_code == 405
    assert response.json() == {
        "error": {
            "code": "method_not_allowed",
            "message": "Method Not Allowed",
            "request_id": "method-request-001",
        },
    }
    assert response.headers["allow"] == "GET"
