"""FastAPI application factory.

One container image serves several handlers; the app is created here and
wrapped by Mangum for Lambda (see lambda handlers in pipeline/ and infra).
Local dev uses uvicorn directly (see Makefile `make api`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response

from dhuan.api.deps import aclose_clients
from dhuan.api.errors import register_error_handlers
from dhuan.api.middleware import ObservabilityMiddleware
from dhuan.api.routers import (
    estimate,
    explain,
    grid,
    health,
    sources,
    stations,
    status,
    subscriptions,
    validation,
)
from dhuan.core.config import get_settings
from dhuan.core.logging import configure_logging

DESCRIPTION = """
**Dhuan Detective API** — street-level PM2.5 estimation, upwind source
attribution and plain-language advice for Delhi-NCR.

Every estimate is a model *estimate* with an uncertainty interval, never a
measurement. Every response reports data age; stale data is served explicitly
rather than invented.
"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield
    await aclose_clients()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Dhuan Detective",
        description=DESCRIPTION,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    register_error_handlers(app)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(ObservabilityMiddleware)

    # routers
    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(stations.router)
    app.include_router(status.router)
    app.include_router(estimate.router)
    app.include_router(grid.router)
    app.include_router(validation.router)
    app.include_router(explain.router)
    app.include_router(subscriptions.router)

    if settings.demo_mode:

        @app.middleware("http")
        async def _demo_banner_header(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            # Rule 1: whenever demo data is served, responses advertise it.
            response = await call_next(request)
            response.headers["X-Dhuan-Demo"] = "1"
            return response

    return app


app = create_app()
