"""RFC 9457 problem+json error handling.

Every error response in the API is `application/problem+json` with a stable
`type` URI, a `title`, `status`, and a `correlation_id` for support. Error
codes are enumerated so the frontend can react programmatically.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from dhuan.core.logging import correlation_id, get_logger

logger = get_logger("api.errors")

PROBLEM_BASE = "https://api.dhuan-detective.example/problems"


class ProblemType(StrEnum):
    VALIDATION = f"{PROBLEM_BASE}/validation"
    NOT_FOUND = f"{PROBLEM_BASE}/not-found"
    OUTSIDE_COVERAGE = f"{PROBLEM_BASE}/outside-coverage"
    RATE_LIMITED = f"{PROBLEM_BASE}/rate-limited"
    UNAUTHORIZED = f"{PROBLEM_BASE}/unauthorized"
    UPSTREAM = f"{PROBLEM_BASE}/upstream"
    NOT_CONFIGURED = f"{PROBLEM_BASE}/not-configured"
    INTERNAL = f"{PROBLEM_BASE}/internal"
    BAD_REQUEST = f"{PROBLEM_BASE}/bad-request"


class Problem(Exception):  # noqa: N818 - RFC 9457 term; name is intentional
    """Raise anywhere in a route to produce a spec-compliant error."""

    def __init__(
        self,
        *,
        problem_type: ProblemType,
        title: str,
        status: int,
        detail: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        log_level: int = 30,
    ) -> None:
        super().__init__(detail or title)
        self.problem_type = problem_type
        self.title = title
        self.status = status
        self.detail = detail
        self.errors = errors
        self.log_level = log_level

    def to_response(self) -> JSONResponse:
        body: dict[str, Any] = {
            "type": str(self.problem_type),
            "title": self.title,
            "status": self.status,
            "correlation_id": correlation_id.get(),
        }
        if self.detail:
            body["detail"] = self.detail
        if self.errors:
            body["errors"] = self.errors
        return JSONResponse(
            body, status_code=self.status, media_type="application/problem+json"
        )


def validation_problem(errors: list[dict[str, Any]]) -> Problem:
    return Problem(
        problem_type=ProblemType.VALIDATION,
        title="Request validation failed",
        status=422,
        detail="One or more fields are missing or invalid.",
        errors=errors,
    )


def outside_coverage_problem(lat: float, lon: float) -> Problem:
    return Problem(
        problem_type=ProblemType.OUTSIDE_COVERAGE,
        title="Point outside coverage",
        status=422,
        detail=(
            f"The point ({lat}, {lon}) is not inside the Delhi-NCR coverage polygon. "
            "Dhuan Detective currently covers Delhi-NCR only."
        ),
        errors=[{"field": "lat/lon", "issue": "outside_delhi_ncr_coverage"}],
    )


def upstream_problem(source: str, detail: str) -> Problem:
    return Problem(
        problem_type=ProblemType.UPSTREAM,
        title=f"Upstream feed unavailable: {source}",
        status=503,
        detail=detail,
    )


def not_configured_problem(source: str) -> Problem:
    return Problem(
        problem_type=ProblemType.NOT_CONFIGURED,
        title=f"Feed not configured: {source}",
        status=503,
        detail=(
            f"The {source} feed is missing its API credential. Set the environment "
            "variable documented in .env.example; no fabricated data is served."
        ),
    )


def not_found_problem(what: str) -> Problem:
    return Problem(
        problem_type=ProblemType.NOT_FOUND,
        title="Not found",
        status=404,
        detail=f"{what} was not found.",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem_handler(_request: Request, exc: Problem) -> JSONResponse:
        logger.log(
            exc.log_level,
            "problem_response",
            extra={
                "problem_type": str(exc.problem_type),
                "status": exc.status,
                "detail": exc.detail,
            },
        )
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in e.get("loc", [])),
                "issue": e.get("type", ""),
                "message": e.get("msg", ""),
            }
            for e in exc.errors()
        ]
        return validation_problem(errors).to_response()

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        mapping = {
            401: ProblemType.UNAUTHORIZED,
            404: ProblemType.NOT_FOUND,
            429: ProblemType.RATE_LIMITED,
            400: ProblemType.BAD_REQUEST,
        }
        problem_type = mapping.get(exc.status_code, ProblemType.INTERNAL)
        return Problem(
            problem_type=problem_type,
            title=exc.detail or "Request failed",
            status=exc.status_code,
            log_level=30,
        ).to_response()

    @app.exception_handler(Exception)
    async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error: %s", exc)
        from dhuan.core.metrics import record  # noqa: PLC0415 - cold-path import

        record("UnhandledErrors", 1)
        return Problem(
            problem_type=ProblemType.INTERNAL,
            title="Internal error",
            status=500,
            detail="An unexpected error occurred. The correlation id identifies it in logs.",
            log_level=50,
        ).to_response()
