"""Global exception handlers and HTTP error models for the cohort API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base application error with a public code and a safe message."""

    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class WarehouseNotFoundError(APIError):
    def __init__(self) -> None:
        super().__init__(
            code="warehouse_not_found",
            message="OMOP warehouse not available. Build it with `make bronze && make omop`.",
            status=503,
        )


class UnauthorizedError(APIError):
    def __init__(self) -> None:
        super().__init__(
            code="unauthorized",
            message="Invalid or missing API key.",
            status=401,
        )


class RateLimitError(APIError):
    def __init__(self) -> None:
        super().__init__(
            code="rate_limited",
            message="Rate limit exceeded. Please slow down.",
            status=429,
        )


def _json(status: int, code: str, message: str, detail: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if detail is not None:
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status, content=body)


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    from .metrics import ERRORS_TOTAL

    ERRORS_TOTAL.labels(error_code=exc.code).inc()
    return _json(exc.status, exc.code, exc.message)


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    # FastAPI/Pydantic validation errors are raised as RequestValidationError
    from fastapi.exceptions import RequestValidationError

    if isinstance(exc, RequestValidationError):
        errors = [
            {"loc": e.get("loc", []), "msg": e.get("msg", "")} for e in exc.errors()
        ]
        return _json(422, "validation_error", "Request validation failed.", errors)
    raise exc


async def catchall_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    from .metrics import ERRORS_TOTAL

    ERRORS_TOTAL.labels(error_code="internal_error").inc()
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _json(
        500,
        "internal_error",
        "An unexpected error occurred. The incident has been logged.",
    )


def register(app) -> None:
    """Attach exception handlers to a FastAPI app."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, catchall_exception_handler)
