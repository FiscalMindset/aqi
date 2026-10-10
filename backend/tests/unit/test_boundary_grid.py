"""Tests for the NCR boundary and H3 grid (deterministic, from real data)."""

from __future__ import annotations

from dhuan.core.units import Bbox, Point
from dhuan.geo.boundary import bbox_of_ncr, point_in_ncr, provenance
from dhuan.geo.grid import cell_boundary, cell_center, cell_for_point, grid_cells, grid_geojson


def test_provenance_present() -> None:
    prov = provenance()
    assert "OpenStreetMap" in prov.get("source", "")
    assert "ODbL" in prov.get("license", "")
    assert prov.get("fetched_utc")


def test_delhi_inside() -> None:
    assert point_in_ncr(Point(28.6139, 77.2090))  # India Gate


def test_noida_inside() -> None:
    assert point_in_ncr(Point(28.5355, 77.3910))  # Noida sector 62


def test_gurugram_inside() -> None:
    assert point_in_ncr(Point(28.4595, 77.0266))


def test_jaipur_outside() -> None:
    assert not point_in_ncr(Point(26.9124, 75.7873))


def test_mumbai_outside() -> None:
    assert not point_in_ncr(Point(19.0760, 72.8777))


def test_bbox_covers_ncr() -> None:
    min_lat, min_lon, max_lat, max_lon = bbox_of_ncr()
    # covers from Bharatpur (south) to Meerut (north-east) and no more
    assert 26.5 < min_lat < 27.0
    assert 76.0 < min_lon < 76.3
    assert 29.4 < max_lat < 29.8
    assert 78.2 < max_lon < 78.6
    b = Bbox(min_lat, min_lon, max_lat, max_lon)
    assert b.contains(Point(28.6139, 77.2090))  # Delhi
    assert b.contains(Point(28.5355, 77.3910))  # Noida


def test_cell_roundtrip() -> None:
    p = Point(28.6139, 77.2090)
    cell = cell_for_point(p)
    center = cell_center(cell)
    assert abs(center.lat - p.lat) < 0.01
    assert abs(center.lon - p.lon) < 0.01


def test_cell_boundary_closed() -> None:
    ring = cell_boundary(cell_for_point(Point(28.6139, 77.2090)))
    assert ring[0] == ring[-1]
    assert len(ring) == 7  # hexagon


def test_grid_cells_deterministic_and_dense() -> None:
    cells = grid_cells(8)
    assert len(cells) > 1000
    assert cell_for_point(Point(28.6139, 77.2090)) in cells
    # sanity: NCT Delhi area ~1484 km2 / ~0.74 km2 per cell ~= 2000 cells minimum
    assert len(cells) >= 2000


def test_grid_geojson_shape() -> None:
    fc = grid_geojson(8)
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == len(grid_cells(8))
