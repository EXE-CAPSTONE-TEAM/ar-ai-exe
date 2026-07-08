from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


ERROR_CODE_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "INVALID_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_413_CONTENT_TOO_LARGE: "INVALID_REQUEST",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "INVALID_REQUEST",
    status.HTTP_429_TOO_MANY_REQUESTS: "QUOTA_EXCEEDED",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
}

DOMAIN_CODE_HINTS = {
    "project": "PROJECT_NOT_FOUND",
    "model asset": "MODEL_NOT_READY",
    "design": "DESIGN_NOT_FOUND",
    "bake": "BAKE_FAILED",
    "export": "EXPORT_FAILED",
}


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc, ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    message = _message_from_detail(exc.detail)
    code = _code_from_exception(exc.status_code, message)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, message),
        headers=exc.headers,
    )


def _safe_input(input_value: Any) -> Any:
    if input_value is None or isinstance(input_value, (str, int, float, bool, list, tuple, dict)):
        try:
            json.dumps(input_value)
            return input_value
        except (TypeError, ValueError):
            return repr(input_value)
    try:
        json.dumps(input_value, default=str)
        return str(input_value)
    except (TypeError, ValueError):
        return repr(input_value)


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    safe_errors = [
        {**err, "input": _safe_input(err.get("input"))}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_payload("INVALID_REQUEST", "Request validation failed.", {"errors": safe_errors}),
    )


def _message_from_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if detail is None:
        return "Unexpected API error."
    return str(detail)


def _code_from_exception(status_code: int, message: str) -> str:
    lowered = message.lower()
    if "unauthorized" in lowered or "missing bearer token" in lowered or status_code == status.HTTP_401_UNAUTHORIZED:
        return "UNAUTHORIZED"
    if "forbidden" in lowered or "invalid or expired access token" in lowered or status_code == status.HTTP_403_FORBIDDEN:
        return "FORBIDDEN"
    if "quota" in lowered:
        return "QUOTA_EXCEEDED"
    if "invalid design" in lowered:
        return "INVALID_DESIGN_CONFIG"
    if status_code == status.HTTP_404_NOT_FOUND:
        for hint, code in DOMAIN_CODE_HINTS.items():
            if hint in lowered:
                return code
    if "bake" in lowered:
        return "BAKE_FAILED"
    if "export" in lowered:
        return "EXPORT_FAILED"
    return ERROR_CODE_BY_STATUS.get(status_code, "INTERNAL_ERROR")
