"""GET /v1/grid — latest H3 grid as GeoJSON (cached, ETag, gzip)."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from dhuan.api.errors import Problem, ProblemType
from dhuan.core.config import Settings, get_settings
from dhuan.geo.grid import grid_cells

router = APIRouter(prefix="/v1", tags=["grid"])


# The full polygon payload for Delhi-NCR at res-8 is ~17.8 MB. API Gateway REST
# caps a response at 10 MB, so the complete geometry can never be delivered
# through it: the gateway truncates and the client sees a 502 with no
# explanation. Rather than let that happen, ids-only is the default and the
# full form is refused with a typed problem that says why and what to use.
FULL_PAYLOAD_LIMIT_BYTES = 10 * 1024 * 1024


@router.get(
    "/grid",
    summary="H3 res-8 grid cell ids for Delhi-NCR as GeoJSON",
    response_description=(
        "GeoJSON FeatureCollection of grid cells (ETag cached). Cell ids by "
        "default; per-cell polygon geometry is refused because it exceeds the "
        "API Gateway 10 MB response limit."
    ),
)
async def grid(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    include_geometry: Annotated[
        bool,
        Query(description="Include polygon boundaries (refused: exceeds the 10 MB limit)"),
    ] = False,
) -> Response:
    cells = grid_cells(settings.h3_resolution)
    etag_source = f"{settings.model_version}:{len(cells)}:{settings.h3_resolution}"
    etag = f'"{hashlib.sha256(etag_source.encode()).hexdigest()[:16]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    if include_geometry:
        raise Problem(
            problem_type=ProblemType.VALIDATION,
            title="Grid geometry exceeds the response limit",
            status=422,
            detail=(
                f"Delhi-NCR at H3 res-{settings.h3_resolution} is {len(cells)} cells; "
                "their full polygon geometry is about 18 MB, which is above the "
                "10 MB maximum response size of API Gateway REST. Request "
                "simplify=true (the default) for the cell ids, or fetch the "
                "geometry client-side from the cell ids."
            ),
        )
    body = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": c, "geometry": None, "properties": {"cell": c}}
            for c in cells
        ],
    }
    body["model_version"] = settings.model_version
    content = json.dumps(body, separators=(",", ":")).encode()
    return Response(
        content=content,
        media_type="application/geo+json",
        headers={"ETag": etag, "Cache-Control": "public, max-age=300"},
    )
