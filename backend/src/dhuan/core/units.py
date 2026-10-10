"""Immutable value types used across the codebase."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

EARTH_RADIUS_KM: Final = 6371.0088  # IUGG mean Earth radius


@dataclass(frozen=True, slots=True)
class Point:
    """A WGS84 coordinate."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise ValueError(f"latitude out of range: {self.lat}")
        if not -180.0 <= self.lon <= 180.0:
            raise ValueError(f"longitude out of range: {self.lon}")


@dataclass(frozen=True, slots=True)
class Bbox:
    """An inclusive bounding box, min == south/west, max == north/east."""

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def __post_init__(self) -> None:
        if self.min_lat > self.max_lat or self.min_lon > self.max_lon:
            raise ValueError("bbox min must be <= max on both axes")

    def contains(self, p: Point) -> bool:
        return self.min_lat <= p.lat <= self.max_lat and self.min_lon <= p.lon <= self.max_lon

    def center(self) -> Point:
        return Point((self.min_lat + self.max_lat) / 2, (self.min_lon + self.max_lon) / 2)


@dataclass(frozen=True, slots=True)
class Interval:
    """An 80% prediction interval: [low, high] around the point estimate."""

    low: float
    mid: float
    high: float

    def __post_init__(self) -> None:
        if not self.low <= self.mid <= self.high:
            raise ValueError(f"invalid interval: [{self.low}, {self.mid}, {self.high}]")
        if self.low < 0:
            raise ValueError("PM2.5 interval cannot be negative")


def haversine_km(a: Point, b: Point) -> float:
    """Great-circle distance in kilometres between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
