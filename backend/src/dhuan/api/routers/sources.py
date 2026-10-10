"""GET /v1/sources — candidate pollution sources from OpenSearch.

Geo-distance query bounded by radius, then the exact upwind-cone test from
geo/geo_math.py. Every result carries distance, bearing and a transparent
heuristic influence score, plus the ODbL attribution for OSM data.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dhuan.api.deps import get_source_index
from dhuan.api.errors import outside_coverage_problem
from dhuan.api.models import SourceOut, SourcesResponse
from dhuan.api.services import weather_now
from dhuan.core.config import Settings, get_settings
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.store.opensearch import SourceIndex

router = APIRouter(prefix="/v1", tags=["sources"])


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="Pollution sources near a point, optionally upwind-filtered",
    response_description="Ranked candidate sources with distance, bearing and influence.",
)
async def sources(  # noqa: PLR0917 - geo params stay positional
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitude (WGS84)")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitude (WGS84)")],
    radius_km: Annotated[float, Query(ge=0.1, le=50, description="Search radius in km")] = 15.0,
    upwind: Annotated[bool, Query(description="Only sources within the upwind cone")] = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    settings: Settings = Depends(get_settings),
    index: SourceIndex = Depends(get_source_index),
) -> SourcesResponse:
    point = Point(lat=lat, lon=lon)
    if not point_in_ncr(point):
        raise outside_coverage_problem(lat, lon)

    wind_deg: float | None = None
    if upwind:
        outcome = await weather_now(lat, lon, settings)
        if outcome.data is not None:
            wind_deg = outcome.data.wind_direction_deg

    hits = index.sources_near(
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        upwind=bool(upwind and wind_deg is not None),
        wind_from_deg=wind_deg,
        limit=limit,
    )
    sources = [
        SourceOut(
            osm_id=str(h.get("osm_id", "")),
            type=str(h.get("type", "other")),
            name=str(h.get("name", "")),
            latitude=float(h["location"]["lat"]),
            longitude=float(h["location"]["lon"]),
            distance_km=float(h.get("distance_km", 0.0)),
            bearing_deg=float(h.get("bearing_deg", 0.0)),
            in_upwind_cone=bool(h.get("in_upwind_cone", False)),
            influence_score=float(h.get("influence_score", 0.0)),
            area_m2=h.get("area_m2"),
        )
        for h in hits
    ]
    return SourcesResponse(
        query={"lat": lat, "lon": lon, "radius_km": radius_km, "upwind": upwind, "limit": limit},
        wind_from_deg=wind_deg,
        count=len(sources),
        sources=sources,
    )
