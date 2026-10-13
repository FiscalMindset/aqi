"""FastAPI application factory.

One container image serves several handlers; the app is created here and
wrapped by Mangum for Lambda (see lambda handlers in pipeline/ and infra).
Local dev uses uvicorn directly (see Makefile `make api`).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from dhuan.api.deps import aclose_clients
from dhuan.api.errors import register_error_handlers
from dhuan.api.middleware import ObservabilityMiddleware
from dhuan.api.routers import (
    alert_preview,
    estimate,
    explain,
    grid,
    health,
    model_card,
    routes,
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


def _mount_spa(app: FastAPI, web_dir: Path, base_path: str = "") -> None:
    """Serve the built SPA with a catch-all fallback to index.html.

    `base_path` is the prefix the app is served under (`/staging` in AWS). The
    built bundle requests its assets, its service worker and its manifest
    relative to that prefix, so the catch-all has to strip it before looking
    for a file on disk. Without this, `/staging/sw.js` resolved to no file and
    fell through to index.html: the browser got HTML where it expected
    JavaScript, the service worker never registered, and the precache from an
    older deploy kept serving references to chunk hashes that no longer exist -
    which surfaced as "Failed to fetch dynamically imported module".
    """
    from fastapi.staticfiles import StaticFiles  # noqa: PLC0415

    prefix = base_path.strip("/")
    assets = web_dir / "assets"
    if assets.is_dir():
        app.mount(f"/{prefix}/assets" if prefix else "/assets",
                  StaticFiles(directory=assets), name="assets")

    index = web_dir / "index.html"
    root = web_dir.resolve()

    # Hashed filenames change whenever the bundle changes, so they are safe to
    # cache forever. index.html and the service worker must not be: they are the
    # documents that *reference* those hashes, and a stale copy points at
    # assets that were deleted by the next deploy.
    immutable_headers = {"Cache-Control": "public, max-age=31536000, immutable"}
    revalidate_headers = {"Cache-Control": "no-cache, must-revalidate"}

    def _serve(candidate: Path) -> FileResponse:
        in_assets = candidate.parent.name == "assets"
        return FileResponse(
            candidate,
            headers=immutable_headers if in_assets else revalidate_headers,
        )

    if prefix:
        root_path = f"/{prefix}"

        @app.get(root_path, include_in_schema=False, response_model=None)
        @app.get(f"{root_path}/", include_in_schema=False, response_model=None)
        async def spa_prefixed_root() -> FileResponse:
            return _serve(index)

    # response_model=None: a union of Starlette response classes is not a valid
    # Pydantic field, and FastAPI raises FastAPIError at import time otherwise.
    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa_catch_all(full_path: str) -> FileResponse | JSONResponse:
        """Client-side routes (/methodology, /subscribe, ...) all return the
        SPA shell; the router resolves them in the browser."""
        if full_path.startswith(("health", "ready", "v1/", "docs", "redoc", "openapi.json")):
            return JSONResponse(
                status_code=404,
                content={
                    "type": "https://api.dhuan-detective.example/problems/not-found",
                    "title": "Not Found",
                    "status": 404,
                },
            )
        # strip the deployment prefix so `/staging/sw.js` looks for `sw.js`
        # version.json is served by the SPA static mount, never cached, so the
        # running bundle can prove whether it is the current build.
        relative = (
            full_path[len(prefix) + 1:]
            if prefix and full_path.startswith(prefix)
            else full_path
        )
        candidate = (root / relative).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return _serve(candidate)
        return _serve(index)


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Dhuan Detective",
        description=DESCRIPTION,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
        # 3.0.x is what our committed spec and the tooling (Schemathesis,
        # Redoc, codegen) validate against
        openapi_version="3.0.3",
    )
    register_error_handlers(app)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        # a cross-origin frontend needs the correlation id to report a problem
        expose_headers=["X-Correlation-Id"],
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
    app.include_router(model_card.router)
    app.include_router(alert_preview.router)
    app.include_router(routes.router)

    # ------------------------------------------------------------------ SPA --
    # The built web app is served by the same Lambda that serves the API, so
    # there is exactly one public URL. Before this existed the app was hosted
    # only in S3, which has two problems: the REST endpoint does not resolve
    # "/" to index.html (403), and the website hostname is not resolvable from
    # every network. Both showed up as React's "Unexpected Application Error!
    # 404 Not Found" for every deep link.
    if settings.web_dir and Path(settings.web_dir).is_dir():
        _mount_spa(app, Path(settings.web_dir), settings.web_base_path)
    else:
        logger.info("web_dir not set or missing; API only (no SPA)")

    return app


app = create_app()
