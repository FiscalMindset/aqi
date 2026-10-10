"""Property and example tests for geo math (Hypothesis + golden cases)."""

from __future__ import annotations

import math

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from dhuan.core.units import Point, haversine_km
from dhuan.geo.geo_math import (
    angle_diff_deg,
    compass_label,
    destination_point,
    initial_bearing_deg,
    is_upwind,
    point_in_ring,
)

lat = st.floats(min_value=-89.0, max_value=89.0)
lon = st.floats(min_value=-179.0, max_value=179.0)
point_st = st.builds(Point, lat=lat, lon=lon)


def test_bearing_north_is_zero() -> None:
    a = Point(0.0, 0.0)
    b = Point(1.0, 0.0)
    assert initial_bearing_deg(a, b) == 0.0


def test_bearing_east_is_ninety() -> None:
    a = Point(0.0, 0.0)
    b = Point(0.0, 1.0)
    assert abs(initial_bearing_deg(a, b) - 90.0) < 1e-9


def test_angle_diff_wraparound() -> None:
    assert angle_diff_deg(0.0, 350.0) == 10.0
    assert angle_diff_deg(350.0, 0.0) == 10.0
    assert angle_diff_deg(90.0, 270.0) == 180.0
    assert angle_diff_deg(10.0, 10.0) == 0.0


def test_upwind_source_detected() -> None:
    # target at origin; source 5 km north; wind from the north (0 deg)
    target = Point(28.6, 77.2)
    source = destination_point(target, 0.0, 5.0)
    assert is_upwind(source, target, wind_from_deg=0.0)


def test_downwind_source_not_in_cone() -> None:
    target = Point(28.6, 77.2)
    source = destination_point(target, 180.0, 5.0)  # to the south
    assert not is_upwind(source, target, wind_from_deg=0.0)


def test_cone_edge_wraparound() -> None:
    target = Point(28.6, 77.2)
    # bearing 350 from target, wind from 350 -> dead upwind
    source = destination_point(target, 350.0, 5.0)
    assert is_upwind(source, target, wind_from_deg=350.0)
    # wind shifted by 44 deg: still inside the +-45 cone
    assert is_upwind(source, target, wind_from_deg=34.0)


def test_point_in_ring_square() -> None:
    square = [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]
    assert point_in_ring(Point(0.5, 0.5), square)
    assert not point_in_ring(Point(1.5, 0.5), square)


def test_destination_distance_roundtrip() -> None:
    origin = Point(28.6, 77.2)
    for bearing in (0.0, 73.0, 180.0, 359.0):
        dest = destination_point(origin, bearing, 12.5)
        assert abs(haversine_km(origin, dest) - 12.5) < 0.01


def test_compass_labels() -> None:
    assert compass_label(0.0) == "N"
    assert compass_label(90.0) == "E"
    assert compass_label(359.0) == "N"


@given(bearing=st.floats(min_value=-720.0, max_value=720.0))
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
def test_angle_diff_bounds(bearing: float) -> None:
    d = angle_diff_deg(bearing, 0.0)
    assert 0.0 <= d <= 180.0


@given(a=point_st, b=point_st)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=40)
def test_bearing_in_range(a: Point, b: Point) -> None:
    if a == b:
        return
    brg = initial_bearing_deg(a, b)
    assert 0.0 <= brg < 360.0
    assert math.isfinite(brg)
    back = initial_bearing_deg(b, a)
    assert angle_diff_deg(brg, back) <= 180.0


@given(a=point_st, wind=st.floats(min_value=-360.0, max_value=720.0))
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=40)
def test_is_upwind_symmetric_in_wind_normalization(a: Point, wind: float) -> None:
    target = Point(28.6, 77.2)
    source = a if a != target else destination_point(target, 0.0, 3.0)
    assert is_upwind(source, target, wind) == is_upwind(source, target, wind % 360.0)
