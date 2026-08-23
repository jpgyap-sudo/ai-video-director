"""RFC 9457 problem-details error responses.

Every API error is emitted as `application/problem+json` with a stable
`type`, `title`, `status`, and `detail`. This is the single error envelope
consumed by the generated TypeScript client.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"

# Stable, documented problem types. The base URI is a placeholder until a
# public docs site exists; each type is a stable slug.
PROBLEM_BASE = "https://ai-video-director.dev/problems"


def _problem(
    status_code: int,
    title: str,
    detail: str,
    type_slug: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE}/{type_slug}",
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON)


def _slug_for_status(status_code: int) -> str:
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "bad-request"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "unauthorized"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not-found"
    if status_code == status.HTTP_409_CONFLICT:
        return "conflict"
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return "validation-error"
    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        return "service-unavailable"
    return "error"


def register_problem_handlers(app: FastAPI) -> None:
    """Attach RFC 9457 handlers for HTTPException and validation errors."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            # FastAPI sometimes passes a dict detail; surface it as extra fields.
            extra = dict(detail)
            message = str(extra.pop("message", exc.detail))
        else:
            extra = None
            message = str(detail)
        return _problem(
            exc.status_code,
            _title_for_status(exc.status_code),
            message,
            _slug_for_status(exc.status_code),
            extra,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return _problem(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Validation error",
            "The request body or parameters failed validation.",
            "validation-error",
            {"errors": errors},
        )


def _title_for_status(status_code: int) -> str:
    titles = {
        status.HTTP_400_BAD_REQUEST: "Bad request",
        status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        status.HTTP_403_FORBIDDEN: "Forbidden",
        status.HTTP_404_NOT_FOUND: "Not found",
        status.HTTP_409_CONFLICT: "Conflict",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "Validation error",
        status.HTTP_503_SERVICE_UNAVAILABLE: "Service unavailable",
    }
    return titles.get(status_code, "Error")
