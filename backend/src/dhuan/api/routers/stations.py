"""GET /v1/stations — nearest official stations with latest PM2.5 and freshness."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dhuan.api.errors import outside_coverage_problem
from dhuan.api.models import StationOut
from dhuan.api.services import category_of, stations_near
from dhuan.core.config import Settings, get_settings
from dhuan.core.units import Point, haversine_km
from dhuan.geo.boundary import point_in_ncr

router = APIRouter(prefix="/v1", tags=["stations"])


@router.get(
    "/stations",
    response_model=list[StationOut],
    summary="Nearest CPCB/OpenAQ stations with latest PM2.5",
    response_description="Stations ordered by distance, with reading age and category.",
    response_model_exclude_none=False,
)
async def stations(
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitude")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitude")],
    limit: Annotated[int, Query(ge=1, le=50, description="Maximum stations")] = 10,
    settings: Settings = Depends(get_settings),
) -> list[StationOut]:
    point = Point(lat=lat, lon=lon)
    if not point_in_ncr(point):
        raise outside_coverage_problem(lat, lon)

    outcome = await stations_near(lat, lon, settings)
    readings = sorted(outcome.data or [], key=lambda r: haversine_km(point, r.location))
    out: list[StationOut] = []
    for r in readings[:limit]:
        out.append(
            StationOut(
                station_id=r.station_id,
                name=r.name,
                latitude=r.location.lat,
                longitude=r.location.lon,
                provider=r.provider,
                distance_km=round(haversine_km(point, r.location), 2),
                pm25=r.value,
                observed_at=r.observed_at.isoformat(),
                age_seconds=round(r.age_seconds(), 1),
                category=category_of(r.value),
            )
        )
    return out
