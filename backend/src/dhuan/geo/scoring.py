"""Transparent, documented heuristic for ranking candidate contributors.

*** This is NOT a causal model. *** It ranks *candidate* sources so an agent
or a human can investigate. The weights below are hand-set priors, stated in
`docs/MODEL_CARD.md`, versioned with the code, and easy to disagree with.

Score = type_weight * size_factor * distance_decay * wind_alignment
where each factor is a documented, bounded prior. The result is in (0, 1].
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dhuan.core.units import Point, haversine_km
from dhuan.geo.geo_math import UPWIND_CONE_HALF_ANGLE_DEG, angle_diff_deg, initial_bearing_deg

# --- hand-set priors (version these with the model card) -------------------
TYPE_WEIGHTS: dict[str, float] = {
    "landfill": 1.00,
    "brick_kiln": 0.85,
    "industrial": 0.80,
    "construction": 0.55,
    "major_junction": 0.35,
    "waste_burning": 0.95,
    "other": 0.20,
}
DEFAULT_TYPE_WEIGHT = 0.20

DISTANCE_DECAY_KM = 6.0  # e^-1 factor at 6 km
MIN_WIND_ALIGNMENT = 0.10  # crosswind floor so nothing is exactly zero
MIN_SIZE_AREA_M2 = 1_000.0
SIZE_AREA_FLOOR_FACTOR = 0.30
SIZE_LOG_REFERENCE = 4.0  # log10(10_000 m^2 == 1 ha)


def size_factor(area_m2: float | None) -> float:
    """Log-scaled area factor in [0.30, 1.0]; unknown area -> 0.55 (middle)."""
    if area_m2 is None or area_m2 <= 0:
        return 0.55
    scaled = math.log10(max(area_m2, MIN_SIZE_AREA_M2)) / SIZE_LOG_REFERENCE
    return SIZE_AREA_FLOOR_FACTOR + (1.0 - SIZE_AREA_FLOOR_FACTOR) * min(scaled, 1.0)


def distance_decay(distance_km: float) -> float:
    if distance_km <= 0:
        return 1.0
    return math.exp(-distance_km / DISTANCE_DECAY_KM)


def wind_alignment(bearing_delta_deg: float) -> float:
    """1.0 dead-upwind, falling to MIN_WIND_ALIGNMENT at the cone edge and beyond."""
    if bearing_delta_deg <= UPWIND_CONE_HALF_ANGLE_DEG:
        return 1.0
    if bearing_delta_deg >= 180.0:
        return MIN_WIND_ALIGNMENT
    # smooth cosine falloff from the cone edge to directly crosswind
    over = (bearing_delta_deg - UPWIND_CONE_HALF_ANGLE_DEG) / (180.0 - UPWIND_CONE_HALF_ANGLE_DEG)
    return 1.0 + (MIN_WIND_ALIGNMENT - 1.0) * over


@dataclass(slots=True)
class CandidateSource:
    """A source as needed by the scorer (subset of the OpenSearch document)."""

    osm_id: str
    name: str
    source_type: str
    location: Point
    area_m2: float | None = None
    tags: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class Influence:
    source: CandidateSource
    distance_km: float
    bearing_deg: float
    score: float
    in_cone: bool


def influence_score(
    source: CandidateSource,
    target: Point,
    wind_from_deg: float,
) -> Influence:
    """Heuristic influence of `source` on `target` given wind direction."""
    distance_km = haversine_km(target, source.location)
    bearing_to_source = initial_bearing_deg(target, source.location)
    delta = angle_diff_deg(bearing_to_source, wind_from_deg)
    score = (
        TYPE_WEIGHTS.get(source.source_type, DEFAULT_TYPE_WEIGHT)
        * size_factor(source.area_m2)
        * distance_decay(distance_km)
        * wind_alignment(delta)
    )
    return Influence(
        source=source,
        distance_km=distance_km,
        bearing_deg=bearing_to_source,
        score=round(min(score, 1.0), 6),
        in_cone=delta <= UPWIND_CONE_HALF_ANGLE_DEG,
    )


def band_for_score(score: float) -> str:
    """Coarse label used in UI copy: High / Medium / Low."""
    if score >= 0.45:
        return "High"
    if score >= 0.20:
        return "Medium"
    return "Low"
