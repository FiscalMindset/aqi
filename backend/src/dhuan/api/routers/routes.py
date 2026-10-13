"""POST /v1/routes/compare — which way to go is cleaner right now.

The product's fourth pillar ("act"): given two points, ask the real road network
for alternative corridors, sample PM2.5 along each one with the same estimator
the rest of the API uses, and rank them by exposure.

Exposure is reported three ways because they answer different questions:
  * mean      - length-weighted average concentration along the corridor
  * peak      - the worst single sample; this is what a person on that stretch
                actually breathes
  * dose      - mean x time in the vehicle/foot; the same average over a longer
                detour is more exposure, and a user should see that trade-off
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from dhuan.api.errors import outside_coverage_problem, upstream_problem
from dhuan.api.schemas import (
    RouteCompareRequest,
    RouteCompareResponse,
    RouteCorridor,
    RouteSample,
)
from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.core.metrics import record
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.ingest.osrm import fetch_routes, straight_line_fallback

router = APIRouter(prefix="/v1", tags=["routes"])
logger = get_logger("api.routes")

# Sampling many points concurrently keeps the wall-clock bounded regardless of
# how many model passes a corridor needs.
MAX_CONCURRENT_ESTIMATES = 6


@router.post(
    "/routes/compare",
    summary="Compare real road routes by estimated PM2.5 exposure",
    response_description="Corridors ranked cleanest first, with a sampled profile.",
)
async def compare_routes(
    body: RouteCompareRequest,
    settings: Settings = Depends(get_settings),
) -> RouteCompareResponse:
    origin = Point(lat=body.from_lat, lon=body.from_lon)
    destination = Point(lat=body.to_lat, lon=body.to_lon)
    for p in (origin, destination):
        if not point_in_ncr(p):
            raise outside_coverage_problem(p.lat, p.lon)

    try:
        candidates = await fetch_routes(
            origin, destination, alternatives=True, settings=settings
        )
        router_used = True
    except Exception as exc:
        logger.warning("router_unavailable_using_straight_line: %s", exc)
        candidates = straight_line_fallback(origin, destination)
        router_used = False

    corridors: list[RouteCorridor] = []
    for rank, route in enumerate(candidates, start=1):
        samples = await _profile(route.samples, settings, body.max_samples)
        usable = [s for s in samples if s.pm25_mid is not None]
        if not usable:
            continue
        mean_pm25 = sum(s.pm25_mid or 0.0 for s in usable) / len(usable)
        peak = max(usable, key=lambda s: s.pm25_mid or 0.0)
        hours = route.duration_s / 3600.0 if route.duration_s else 0.0
        corridors.append(
            RouteCorridor(
                rank=rank,
                kind=route.kind,
                distance_km=round(route.distance_m / 1000.0, 2),
                duration_min=round(route.duration_s / 60.0, 1),
                mean_pm25=round(mean_pm25, 1),
                peak_pm25=round(peak.pm25_mid or 0.0, 1),
                peak_at={"lat": peak.lat, "lon": peak.lon},
                dose_index=round(mean_pm25 * hours, 1) if hours else None,
                served_points=len(usable),
                # The road polyline the router returned, not the handful of
                # points we sampled for PM2.5. Returning the sample points as
                # "geometry" drew a straight line between 12 dots and made a
                # real road look like a fake one.
                geometry=[
                    [round(lon, 5), round(lat, 5)]
                    for lon, lat in _decimate(route.geometry, 120)
                ],
                samples=samples,
            )
        )

    if not corridors:
        raise upstream_problem(
            "openaq", "No usable estimate along any corridor; refusing to rank."
        )

    # Rank by exposure, not by the router's shortest-first order: the whole point
    # is that the quick way is not always the clean way.
    corridors.sort(key=lambda c: (c.mean_pm25, c.distance_km))
    for i, c in enumerate(corridors, start=1):
        c.rank = i

    best = corridors[0]
    worst = corridors[-1]
    saving = round(worst.mean_pm25 - best.mean_pm25, 1)
    record("RouteComparisons", 1)

    return RouteCompareResponse(
        origin={"lat": origin.lat, "lon": origin.lon},
        destination={"lat": destination.lat, "lon": destination.lon},
        router=("osrm" if router_used else "straight-line-fallback"),
        corridor_count=len(corridors),
        corridors=corridors,
        cleanest=best,
        worst=worst,
        mean_pm25_saving=saving,
        samples_per_corridor=body.max_samples,
        note=(
            "Exposure is estimated, not measured. It is the length-weighted mean of "
            "our own PM2.5 estimate sampled along each real road corridor. Official "
            "CPCB station readings remain the authoritative source."
        ),
        honesty_note=(
            "Routes come from the public OSRM demo server. If it was unavailable the "
            "corridors are labelled straight-line and are not real roads."
        ),
    )


def _decimate(
    line: list[tuple[float, float]], limit: int
) -> list[tuple[float, float]]:
    """Thin a polyline to at most `limit` points, keeping both ends.

    A 26 km OSRM road can carry several hundred vertices. Every one of them is
    not needed to draw a corridor, and the payload is sent to a browser.
    """
    if len(line) <= limit:
        return line
    step = (len(line) - 1) / (limit - 1)
    out = [line[round(i * step)] for i in range(limit)]
    out[0] = line[0]
    out[-1] = line[-1]
    return out


async def _profile(
    points: list[Point], settings: Settings, limit: int
) -> list[RouteSample]:
    """Estimate PM2.5 at each sampled point, bounded concurrency."""
    from dhuan.api.routers.estimate import compute_estimate

    chosen = points[: max(2, limit)]
    if len(chosen) >= 2:
        chosen = [*chosen[:-1], points[-1]]  # always keep the destination
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_ESTIMATES)

    async def one(p: Point) -> RouteSample:
        async with semaphore:
            try:
                est = await compute_estimate(p.lat, p.lon, settings, explain=False)
            except Exception as exc:
                logger.warning("route_sample_failed: %s", exc)
                return RouteSample(lat=p.lat, lon=p.lon, pm25_mid=None, category=None)
        return RouteSample(
            lat=p.lat,
            lon=p.lon,
            pm25_mid=est.pm25_mid,
            category=est.category,
            data_age_seconds=round(est.data_age_seconds, 1),
            served_by=est.served_by,
        )

    return list(await asyncio.gather(*(one(p) for p in chosen)))
