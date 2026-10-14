"""Pydantic response models shared across routes (OpenAPI examples included)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from dhuan.model.cpcb import CATEGORIES


class Freshness(BaseModel):
    """Honesty block: how old is the data behind this response."""

    data_age_seconds: float = Field(0, description="Age of the freshest underlying data")
    stale: bool = Field(False, description="True when serving last-good values")
    model_version: str = Field("baseline-v1", description="Model that produced an estimate")
    source_feeds: list[str] = Field(default_factory=list, description="Feeds that answered")


class StationOut(BaseModel):
    station_id: str
    name: str
    latitude: float
    longitude: float
    provider: str
    distance_km: float
    pm25: float | None = None
    observed_at: str | None = None
    age_seconds: float | None = None
    category: Literal[tuple(CATEGORIES)] | None = None  # type: ignore[valid-type]


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str


class ReadyCheck(BaseModel):
    component: str
    ok: bool
    detail: str


class ReadyOut(BaseModel):
    status: Literal["ready", "degraded"]
    checks: list[ReadyCheck]


class FeedStatusOut(BaseModel):
    feed: str
    ok: bool
    last_success_at: str | None
    age_seconds: float | None
    last_error: str | None = None
    records_last_run: int = 0


class StatusOut(BaseModel):
    integrations: dict[str, object] = Field(
        default_factory=dict,
        description="Which optional integrations are configured (presence only, never values)",
    )
    status: Literal["ok", "degraded"]
    api_version: str
    model_version: str
    feeds: list[FeedStatusOut]
    coverage: dict[str, object]


class FeatureContribution(BaseModel):
    """How much one input parameter moved this particular estimate."""

    name: str
    value: float
    unit: str
    reference: float
    contribution_ugm3: float
    absolute_effect_ugm3: float


class EstimateOut(BaseModel):
    """PM2.5 estimate with an 80% interval and full honesty block."""

    lat: float
    lon: float
    ts_utc: str
    pm25_low: float
    pm25_mid: float
    pm25_high: float
    category: str
    aqi_sub_index: int | None = None
    nearest_station_pm25: float | None = None
    nearest_station_name: str | None = None
    data_age_seconds: float
    stale: bool
    model_version: str
    served_by: str  # "model" | "nearest-station"
    cpcb_table_version: str
    honesty: str
    # "Which parameters produced this number?" — answered per prediction.
    persistence_anchor_ugm3: float | None = None
    model_adjustment_ugm3: float | None = None
    features_used: list[FeatureContribution] = []
    method: str = "persistence-baseline"
    # What the air is doing right now. The estimate alone does not tell a user
    # *why* this point differs from the one they came from: wind decides which
    # sources are upstream, and speed decides whether pollution disperses at
    # all. Surfacing it here means the UI can explain the number without
    # a second round trip.
    weather: WeatherOut | None = None
    cross_check: CrossCheckOut | None = None


class CrossCheckOut(BaseModel):
    """An independent second opinion on PM2.5, from a different data chain.

    Deliberately not merged into the estimate and deliberately not labelled a
    source attribution. Our estimate is anchored to a CPCB ground monitor; this
    is a regional CAMS aerosol grid. They are different measurements of the same
    atmosphere, so the gap between them is informative rather than an error.
    """

    pm25_ugm3: float | None = None
    us_aqi: float | None = None
    european_aqi: float | None = None
    dust_ugm3: float | None = None
    # Our estimate minus CAMS. Positive means the local station reads dirtier
    # than the regional picture.
    delta_ugm3: float | None = None
    age_seconds: float | None = None
    provider: str = "Open-Meteo Air Quality (CAMS)"
    # Always explicit so no UI can present this as a ground reading.
    is_ground_reading: bool = False


class WeatherOut(BaseModel):
    """Current conditions at the point, with the derived ventilation verdict."""

    wind_speed_ms: float | None = None
    wind_gust_ms: float | None = None
    wind_from_deg: float | None = None
    wind_from_label: str | None = None
    temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    precipitation_mm: float | None = None
    age_seconds: float | None = None
    stale: bool = False
    # "good" | "moderate" | "poor": how well the air can flush itself here.
    # Derived from wind speed and gusts, never presented as a measurement.
    ventilation: str | None = None
    ventilation_reason: str | None = None


class ModelMetrics(BaseModel):
    """Held-out accuracy for one evaluation protocol."""

    n_train: int
    n_test: int
    mae: float
    rmse: float
    r2: float
    bias: float
    coverage80: float | None = None
    mean_width: float | None = None


class ModelCardOut(BaseModel):
    """Algorithm, accuracy and provenance — regenerated from metrics.json."""

    algorithm: str
    trained_at_utc: str
    snapshot_sha256: str
    n_rows: int
    stations: list[dict[str, object]]
    temporal_holdout: ModelMetrics
    leave_one_station_out: ModelMetrics
    baselines: dict[str, ModelMetrics]
    winner: str
    features: list[str]
    n_features: int
    conformal_radius_ugm3: float
    notes: list[str]


class ValidationOut(BaseModel):
    """Metrics exactly as produced by model/evaluate.py."""

    version: str
    created_utc: str
    n_rows: int
    temporal_holdout: dict[str, object]
    loso_mean: dict[str, object]
    baselines: dict[str, object]
    winner: str
    interval_coverage_note: str = "conformal 80% on the temporal holdout"


class SourceOut(BaseModel):
    osm_id: str
    type: str
    name: str
    latitude: float
    longitude: float
    distance_km: float
    bearing_deg: float
    in_upwind_cone: bool
    influence_score: float
    area_m2: float | None = None
    attribution: str = "© OpenStreetMap contributors (ODbL)"


class SourcesResponse(BaseModel):
    query: dict[str, object]
    wind_from_deg: float | None = None
    count: int
    sources: list[SourceOut]
    openness_note: str = (
        "Influence scores are a transparent heuristic for ranking candidates, "
        "not a causal attribution."
    )
