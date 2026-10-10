"""Delhi-NCR coverage polygon loaded from a real OpenStreetMap extract.

The GeoJSON (with provenance) lives next to this module. Functions here are
pure given the loaded data so they stay easy to test.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any, NamedTuple

from dhuan.core.units import Point
from dhuan.geo.geo_math import point_in_ring

_BOUNDARY_FILE = "ncr_boundary.geojson"


class BoundaryMeta(NamedTuple):
    source: str
    license: str
    fetched_utc: str
    n_polygons: int


@lru_cache
def _load() -> tuple[list[list[list[float]]], dict[str, Any]]:
    ref = resources.files("dhuan.geo").joinpath(_BOUNDARY_FILE)
    data = json.loads(ref.read_text(encoding="utf-8"))
    polys: list[list[list[float]]] = []
    for feature in data.get("features", []):
        geom = feature.get("geometry") or {}
        if geom.get("type") == "Polygon":
            polys.append(geom["coordinates"][0])
        elif geom.get("type") == "MultiPolygon":
            polys.extend(poly[0] for poly in geom["coordinates"])
    return polys, data.get("provenance", {})


def rings() -> list[list[list[float]]]:
    return _load()[0]


def provenance() -> dict[str, Any]:
    return dict(_load()[1])


def point_in_ncr(p: Point) -> bool:
    """True if the point lies inside any NCR district polygon."""
    return any(point_in_ring(p, ring) for ring in rings())


def bbox_of_ncr() -> tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon) of the coverage polygons."""
    lats: list[float] = []
    lons: list[float] = []
    for ring in rings():
        for lon, lat in ring:
            lats.append(lat)
            lons.append(lon)
    return min(lats), min(lons), max(lats), max(lons)
