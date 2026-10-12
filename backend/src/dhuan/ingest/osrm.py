"""OSRM road-network client for the cleanest-route comparison.

Verified against the public demo server (https://project-osrm.org/):
  * `GET /route/v1/driving/{lon1},{lat1};{lon2},{lat2}`
  * `?alternatives=true&geometries=geojson&overview=full&steps=false`
  * `annotations=false`. No key required, no account.

The demo server is explicitly not for production use and has no SLA. If it is
unreachable the route comparison fails soft with a typed problem; it never
fabricates a route.

Every returned geometry is a real road path. Straight-line "corridors" are only
produced when there is exactly one endpoint pair and the router is down, and
they are labelled ``kind="straight-line"`` so the UI can say so.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from dhuan.core.config import Settings, get_settings
from dhuan.core.http import HttpPolicy, UpstreamError, make_client, make_request
from dhuan.core.logging import get_logger
from dhuan.core.units import Point, haversine_km

logger = get_logger("ingest.osrm")

OSRM_BASE = "https://router.project-osrm.org"

# One sample per this many metres along the route. 500 m is fine enough to catch
# a landfill on one side of the road without costing 100 model calls.
SAMPLE_SPACING_M = 500.0
MAX_SAMPLES_PER_ROUTE = 14


@dataclass(slots=True)
class RouteCandidate:
    """One candidate corridor between the two endpoints."""

    distance_m: float
    duration_s: float
    geometry: list[tuple[float, float]]  # (lon, lat), OSRM order
    samples: list[Point] = field(default_factory=list)
    kind: str = "road"


def _haversine(a: Point, b: Point) -> float:
    return haversine_km(a, b) * 1000.0


def sample_along(
    geometry: list[tuple[float, float]], spacing_m: float = SAMPLE_SPACING_M
) -> list[Point]:
    """Evenly spaced points along a polyline, endpoints included."""
    if not geometry:
        return []
    if len(geometry) == 1:
        return [Point(lat=geometry[0][1], lon=geometry[0][0])]

    cumulative = 0.0
    next_target = 0.0
    out: list[Point] = [Point(lat=geometry[0][1], lon=geometry[0][0])]
    for (lon1, lat1), (lon2, lat2) in pairwise(geometry):
        seg = _haversine(Point(lat=lat1, lon=lon1), Point(lat=lat2, lon=lon2))
        if seg <= 0:
            continue
        while next_target <= cumulative + seg + 1e-9:
            # travelled is measured from the START of this segment every time.
            # Guarding this with `if next_target < cumulative` left travelled at
            # 0 for every target inside the segment, so the sampler emitted a
            # run of duplicate points at the segment start and then jumped the
            # whole segment in one step.
            travelled = max(0.0, next_target - cumulative)
            ratio = min(1.0, travelled / seg)
            out.append(
                Point(
                    lat=lat1 + (lat2 - lat1) * ratio,
                    lon=lon1 + (lon2 - lon1) * ratio,
                )
            )
            next_target += spacing_m
            if len(out) >= MAX_SAMPLES_PER_ROUTE:
                break
        cumulative += seg

    last = geometry[-1]
    if _haversine(out[-1], Point(lat=last[1], lon=last[0])) > 50:
        out.append(Point(lat=last[1], lon=last[0]))
    # The first sample lands on the origin, which is already in `out`.
    deduped: list[Point] = [out[0]]
    for p in out[1:]:
        if _haversine(deduped[-1], p) > 1.0:
            deduped.append(p)
    return deduped


async def fetch_routes(
    origin: Point,
    destination: Point,
    *,
    alternatives: bool = True,
    settings: Settings | None = None,
    client: Any = None,
) -> list[RouteCandidate]:
    """Candidate road routes, ranked shortest-first by the router."""
    s = settings or get_settings()
    coords = f"{origin.lon},{origin.lat};{destination.lon},{destination.lat}"
    url = (
        f"{s.osrm_base_url}/route/v1/driving/{coords}"
        f"?alternatives={'true' if alternatives else 'false'}"
        "&geometries=geojson&overview=full&steps=false"
    )
    owned = client is None
    http = client or make_client(HttpPolicy.from_settings(s))
    try:
        resp = await make_request(
            http,
            HttpPolicy.from_settings(s),
            "osrm",
            "GET",
            url,
            timeout=20,
        )
        payload = resp.json()
    finally:
        if owned:
            with suppress(Exception):  # closing must not mask the result
                await http.aclose()

    if payload.get("code") != "Ok":
        raise UpstreamError("osrm", f"router said {payload.get('code')!r}")

    out: list[RouteCandidate] = []
    for route in payload.get("routes") or []:
        coords = (route.get("geometry") or {}).get("coordinates", [])
        geometry = [(float(lon), float(lat)) for lon, lat in coords]
        if len(geometry) < 2:
            continue
        distance = float(route.get("distance") or 0.0)
        if distance <= 0:
            continue
        out.append(
            RouteCandidate(
                distance_m=distance,
                duration_s=float(route.get("duration") or 0.0),
                geometry=geometry,
                samples=sample_along(
                    geometry, max(SAMPLE_SPACING_M, distance / MAX_SAMPLES_PER_ROUTE)
                ),
            )
        )
    if not out:
        raise UpstreamError("osrm", "no usable route geometry returned")
    out.sort(key=lambda r: r.distance_m)
    return out[:4]


def straight_line_fallback(origin: Point, destination: Point) -> list[RouteCandidate]:
    """A labelled direct corridor, used only when the router is unavailable."""
    mid = Point(lat=(origin.lat + destination.lat) / 2, lon=(origin.lon + destination.lon) / 2)
    distance = _haversine(origin, destination)
    return [
        RouteCandidate(
            distance_m=distance,
            duration_s=0.0,
            geometry=[(origin.lon, origin.lat), (destination.lon, destination.lat)],
            samples=[origin, mid, destination],
            kind="straight-line",
        )
    ]


__all__ = [
    "MAX_SAMPLES_PER_ROUTE",
    "OSRM_BASE",
    "RouteCandidate",
    "fetch_routes",
    "sample_along",
    "straight_line_fallback",
]
