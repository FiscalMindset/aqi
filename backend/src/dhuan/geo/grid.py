"""H3 grid helpers (resolution 8 by default, ~0.74 km² cells).

The grid is derived deterministically from the NCR boundary GeoJSON. The
point-in-polygon scan is vectorized with numpy so computing the full grid
takes well under a second.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import h3
import numpy as np

from dhuan.core.units import Point
from dhuan.geo.boundary import rings

GRID_STEP_DEG = 0.004  # ~450 m, well below res-8 cell size


def cell_for_point(p: Point, resolution: int = 8) -> str:
    """H3 cell containing the point."""
    cell: str = h3.latlng_to_cell(p.lat, p.lon, res=resolution)
    return cell


def cell_center(cell: str) -> Point:
    """Centroid of an H3 cell."""
    lat, lon = h3.cell_to_latlng(cell)
    return Point(lat=lat, lon=lon)


def cell_boundary(cell: str) -> list[list[float]]:
    """Cell outline as [lon, lat] pairs (GeoJSON order), closed."""
    latlng_boundary = h3.cell_to_boundary(cell)
    ring = [[lon, lat] for lat, lon in latlng_boundary]
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _ring_arrays() -> list[np.ndarray]:
    return [np.asarray(ring, dtype=float) for ring in rings()]


def _inside_mask(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Vectorized point-in-any-ring test (ray casting per ring, OR-combined)."""
    inside = np.zeros(lats.shape, dtype=bool)
    for arr in _ring_arrays():
        x = arr[:, 0]
        y = arr[:, 1]
        x1, y1 = x[:-1, None], y[:-1, None]
        x2, y2 = x[1:, None], y[1:, None]
        straddle = (y1 > lats[None, :]) != (y2 > lats[None, :])
        with np.errstate(divide="ignore", invalid="ignore"):
            xin = x1 + (lats[None, :] - y1) * (x2 - x1) / (y2 - y1)
        hits = straddle & (lons[None, :] < xin)
        inside ^= hits.any(axis=0)
    return inside


# The cell set is deterministic for a given resolution and costs ~100 s to
# enumerate from the boundary polygon. It is precomputed into the image instead,
# so the route never pays that cost per request.
CELLS_DIR = Path(__file__).resolve().parents[3] / "data"


@lru_cache(maxsize=8)
def _precomputed_cells(resolution: int) -> tuple[str, ...] | None:
    path = CELLS_DIR / f"grid_cells_res{resolution}.json"
    if not path.exists():
        return None
    cached: list[str] = json.loads(path.read_text())
    return tuple(cached)


def grid_cells(resolution: int = 8) -> tuple[str, ...]:
    """All H3 cells whose centroid lands inside the NCR boundary."""
    precomputed = _precomputed_cells(resolution)
    if precomputed is not None:
        return precomputed
    return _enumerate_cells(resolution)


def _enumerate_cells(resolution: int = 8) -> tuple[str, ...]:
    """Enumerate from the boundary polygon. Used when no precomputed file exists."""
    all_lats: list[float] = []
    all_lons: list[float] = []
    for ring in rings():
        for lon, lat in ring:
            all_lats.append(lat)
            all_lons.append(lon)
    if not all_lats:
        return ()
    lats = np.arange(min(all_lats), max(all_lats) + GRID_STEP_DEG / 2, GRID_STEP_DEG)
    lons = np.arange(min(all_lons), max(all_lons) + GRID_STEP_DEG / 2, GRID_STEP_DEG)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    lat_flat = lat_grid.ravel()
    lon_flat = lon_grid.ravel()
    mask = _inside_mask(lat_flat, lon_flat)
    cells = {
        h3.latlng_to_cell(float(la), float(lo), res=resolution)
        for la, lo in zip(lat_flat[mask].tolist(), lon_flat[mask].tolist(), strict=True)
    }
    return tuple(sorted(cells))


def grid_geojson(resolution: int = 8) -> dict[str, object]:
    """GeoJSON FeatureCollection of grid cells (no properties)."""
    features = [
        {
            "type": "Feature",
            "id": cell,
            "geometry": {"type": "Polygon", "coordinates": [cell_boundary(cell)]},
            "properties": {"cell": cell},
        }
        for cell in grid_cells(resolution)
    ]
    return {"type": "FeatureCollection", "features": features}


def grid_cell_count(resolution: int = 8) -> int:
    return len(grid_cells(resolution))
