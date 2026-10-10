"""GET /v1/grid — latest H3 grid as GeoJSON (cached, ETag, gzip)."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from dhuan.core.config import Settings, get_settings
from dhuan.geo.grid import cell_boundary, grid_cells

router = APIRouter(prefix="/v1", tags=["grid"])


@router.get(
    "/grid",
    summary="Latest H3 res-8 grid for Delhi-NCR as GeoJSON",
    response_description="GeoJSON FeatureCollection of grid cells (ETag cached).",
)
async def grid(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    simplify: Annotated[bool, Query(description="Omit per-cell polylines (ids only)")] = False,
) -> Response:
    cells = grid_cells(settings.h3_resolution)
    etag_source = f"{settings.model_version}:{len(cells)}:{settings.h3_resolution}"
    etag = f'"{hashlib.sha256(etag_source.encode()).hexdigest()[:16]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    if simplify:
        body = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "id": c, "geometry": None, "properties": {"cell": c}}
                for c in cells
            ],
        }
    else:
        body = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": c,
                    "geometry": {"type": "Polygon", "coordinates": [cell_boundary(c)]},
                    "properties": {"cell": c},
                }
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
