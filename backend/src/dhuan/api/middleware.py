"""Middleware: correlation id, structured access log, timing, metrics."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from dhuan.core.logging import correlation_id, get_logger
from dhuan.core.metrics import record

logger = get_logger("api.access")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Assign/propagate a correlation id and log one line per request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-correlation-id")
        correlation_id.set(incoming or uuid.uuid4().hex[:16])
        cid = correlation_id.get()
        request.state.correlation_id = cid
        start = time.perf_counter()
        response: Response | None = None
        error: Exception | None = None
        try:
            response = await call_next(request)
        except Exception as exc:  # let the global handler respond; log here first
            error = exc
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            status = response.status_code if response is not None else 500
            if response is not None:
                response.headers["X-Correlation-Id"] = cid
            record("Requests", 1)
            record("Latency", duration_ms, "Milliseconds")
            if status >= 500:
                record("ServerErrors", 1)
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(error) if error else None,
                },
            )
        return response
