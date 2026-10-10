"""Tests for the influence-score heuristic and its documented bounds."""

from __future__ import annotations

from dhuan.core.units import Point
from dhuan.geo.geo_math import destination_point
from dhuan.geo.scoring import (
    CandidateSource,
    band_for_score,
    distance_decay,
    influence_score,
    size_factor,
    wind_alignment,
)


def _source(
    lat: float, lon: float, stype: str = "landfill", area: float | None = 100_000.0
) -> CandidateSource:
    return CandidateSource(
        osm_id="way/1", name="Test site", source_type=stype, location=Point(lat, lon), area_m2=area
    )


def test_dead_upwind_scores_high() -> None:
    target = Point(28.6, 77.2)
    src = _source(*_latlon(destination_point(target, 0.0, 2.0)))
    influence = influence_score(src, target, wind_from_deg=0.0)
    assert influence.in_cone
    assert influence.score > 0.4
    assert band_for_score(influence.score) in {"High", "Medium"}


def _latlon(p: Point) -> tuple[float, float]:
    return p.lat, p.lon


def test_far_source_decays() -> None:
    target = Point(28.6, 77.2)
    near = influence_score(_source(*_latlon(destination_point(target, 0.0, 1.0))), target, 0.0)
    far = influence_score(_source(*_latlon(destination_point(target, 0.0, 30.0))), target, 0.0)
    assert near.score > far.score
    assert far.score >= 0.0


def test_type_weights_monotone() -> None:
    target = Point(28.6, 77.2)
    landfill = influence_score(_source(28.65, 77.25, "landfill"), target, 315.0)
    junction = influence_score(_source(28.65, 77.25, "major_junction"), target, 315.0)
    assert landfill.score > junction.score


def test_wind_alignment_bounds() -> None:
    assert wind_alignment(0.0) == 1.0
    assert wind_alignment(45.0) == 1.0
    assert wind_alignment(180.0) >= 0.1


def test_size_factor_bounds() -> None:
    assert size_factor(None) == 0.55
    assert 0.3 <= size_factor(10.0) <= 1.0
    assert size_factor(1e6) == 1.0


def test_distance_decay_monotone() -> None:
    assert distance_decay(0.0) == 1.0
    assert distance_decay(10.0) < distance_decay(5.0) < distance_decay(2.0)


def test_score_never_above_one() -> None:
    target = Point(28.6, 77.2)
    for stype in ("landfill", "industrial", "construction", "other"):
        src = _source(28.600001, 77.200001, stype, area=1e9)
        assert influence_score(src, target, 0.0).score <= 1.0


def test_band_thresholds() -> None:
    assert band_for_score(0.5) == "High"
    assert band_for_score(0.3) == "Medium"
    assert band_for_score(0.05) == "Low"
