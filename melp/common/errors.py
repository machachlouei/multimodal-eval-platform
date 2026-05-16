"""Problem+JSON error format. See §8.4."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class MELPError(HTTPException):
    code: str = "INTERNAL_ERROR"
    status: int = 500

    def __init__(self, message: str, *, details: list[dict[str, Any]] | None = None):
        super().__init__(status_code=self.status, detail=message)
        self.message = message
        self.details = details or []


class ValidationFailed(MELPError):
    code = "VALIDATION_FAILED"
    status = 400


class Unauthenticated(MELPError):
    code = "UNAUTHENTICATED"
    status = 401


class Forbidden(MELPError):
    code = "FORBIDDEN"
    status = 403


class NotFound(MELPError):
    code = "NOT_FOUND"
    status = 404


class Conflict(MELPError):
    code = "CONFLICT"
    status = 409


class RateLimited(MELPError):
    code = "RATE_LIMITED"
    status = 429


class QuotaExceeded(MELPError):
    code = "QUOTA_EXCEEDED"
    status = 429


async def melp_error_handler(request: Request, exc: MELPError) -> JSONResponse:
    payload = {
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
        "request_id": request.headers.get("x-request-id", ""),
    }
    return JSONResponse(status_code=exc.status, content=payload)


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": str(exc),
            "details": [],
            "request_id": request.headers.get("x-request-id", ""),
        },
    )
