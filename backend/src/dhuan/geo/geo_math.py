"""Pure geospatial math. No I/O, no state — every function here is unit and
property tested (Hypothesis), including 0/360-degree wrap-around.
"""

from __future__ import annotations

import math

from dhuan.core.units import EARTH_RADIUS_KM, Point

UPWIND_CONE_HALF_ANGLE_DEG = 45.0


def initial_bearing_deg(a: Point, b: Point) -> float:
    """Initial great-circle bearing from `a` to `b`, degrees clockwise from true north."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y)) % 360.0
    # float safety: tiny negatives can modulo to exactly 360.0
    return 0.0 if bearing >= 360.0 else bearing


def angle_diff_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings in degrees (0..180)."""
    d = abs(a - b) % 360.0
    return d if d <= 180.0 else 360.0 - d


def is_upwind(
    source: Point,
    target: Point,
    wind_from_deg: float,
    cone_half_angle_deg: float = UPWIND_CONE_HALF_ANGLE_DEG,
) -> bool:
    """True when `source` lies within the upwind cone as seen from `target`.

    `wind_from_deg` is the meteorological "wind FROM" direction (degrees
    clockwise from north, the convention used by every weather API we call).
    A source upwind of the target therefore lies along bearing
    `wind_from_deg` from the target.
    """
    bearing_to_source = initial_bearing_deg(target, source)
    return angle_diff_deg(bearing_to_source, wind_from_deg) <= cone_half_angle_deg


def destination_point(origin: Point, bearing_deg: float, distance_km: float) -> Point:
    """Point reached by travelling `distance_km` on the given initial bearing."""
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    theta = math.radians(bearing_deg)
    dr = distance_km / EARTH_RADIUS_KM
    lat2 = math.asin(
        math.sin(lat1) * math.cos(dr) + math.cos(lat1) * math.sin(dr) * math.cos(theta)
    )
    lon2 = lon1 + math.atan2(
        math.sin(theta) * math.sin(dr) * math.cos(lat1),
        math.cos(dr) - math.sin(lat1) * math.sin(lat2),
    )
    lon2 = math.degrees(lon2)
    return Point(lat=math.degrees(lat2), lon=((lon2 + 540.0) % 360.0) - 180.0)


def km_per_deg_lon(lat: float) -> float:
    """East-west kilometres per degree of longitude at a latitude."""
    return 111.320 * math.cos(math.radians(lat))


def point_in_ring(p: Point, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon. `ring` is [lon, lat] pairs, closed."""
    x, y = p.lon, p.lat
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def bearing_of_vector(dx_km: float, dy_km: float) -> float:
    """Bearing of an east/north offset pair in km (x=east, y=north)."""
    brg = math.degrees(math.atan2(dx_km, dy_km)) % 360.0
    return 0.0 if brg >= 360.0 else brg


def compass_label(bearing_deg: float) -> str:
    """16-point compass label for a wind direction."""
    labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return labels[int(((bearing_deg % 360.0) + 11.25) // 22.5) % 16]
