"""Standardized API error response schemas."""

from pydantic import BaseModel, ConfigDict


class ValidationIssue(BaseModel):
    """A sanitized request-validation issue."""

    model_config = ConfigDict(frozen=True)

    location: list[str | int]
    message: str
    type: str


class ErrorDetail(BaseModel):
    """Machine-readable and human-readable API error details."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    request_id: str
    validation_issues: list[ValidationIssue] | None = None


class ErrorResponse(BaseModel):
    """Standard API error response envelope."""

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail
