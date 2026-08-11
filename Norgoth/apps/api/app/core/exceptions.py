"""Application-wide exception handling."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.middleware.request_context import (
    apply_standard_response_headers,
)
from app.schemas.errors import (
    ErrorDetail,
    ErrorResponse,
    ValidationIssue,
)

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)

    if isinstance(request_id, str):
        return request_id

    return "unavailable"


def _create_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    validation_issues: list[ValidationIssue] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=request_id,
            validation_issues=validation_issues,
        ),
    )

    response = JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )

    apply_standard_response_headers(
        response,
        request_id=request_id,
    )

    return response


def _get_http_error_code(status_code: int) -> str:
    if status_code == 404:
        return "not_found"

    if status_code == 405:
        return "method_not_allowed"

    return "http_error"


def register_exception_handlers(application: FastAPI) -> None:
    """Register standardized application exception handlers."""

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exception: StarletteHTTPException,
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        message = (
            exception.detail
            if isinstance(exception.detail, str)
            else "The request could not be completed."
        )

        response_headers = dict(exception.headers) if exception.headers is not None else None

        return _create_error_response(
            status_code=exception.status_code,
            code=_get_http_error_code(exception.status_code),
            message=message,
            request_id=request_id,
            headers=response_headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        validation_issues = [
            ValidationIssue(
                location=[item for item in error["loc"] if isinstance(item, str | int)],
                message=str(error["msg"]),
                type=str(error["type"]),
            )
            for error in exception.errors()
        ]

        return _create_error_response(
            status_code=422,
            code="request_validation_failed",
            message="The request did not pass validation.",
            request_id=request_id,
            validation_issues=validation_issues,
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        logger.error(
            "Unhandled application exception: request_id=%s",
            request_id,
            exc_info=exception,
        )

        return _create_error_response(
            status_code=500,
            code="internal_server_error",
            message="An unexpected server error occurred.",
            request_id=request_id,
        )
