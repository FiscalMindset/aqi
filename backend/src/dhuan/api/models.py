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
    demo_mode: bool = Field(False, description="True when DEMO_MODE is serving recorded data")


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
    demo_mode: bool


class ReadyCheck(BaseModel):
    component: str
    ok: bool
    detail: str


class ReadyOut(BaseModel):
    status: Literal["ready", "degraded"]
    checks: list[ReadyCheck]
    demo_mode: bool


class FeedStatusOut(BaseModel):
    feed: str
    ok: bool
    last_success_at: str | None
    age_seconds: float | None
    last_error: str | None = None
    records_last_run: int = 0


class StatusOut(BaseModel):
    status: Literal["ok", "degraded"]
    api_version: str
    model_version: str
    feeds: list[FeedStatusOut]
    coverage: dict[str, object]
    demo_mode: bool


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
    demo_mode: bool


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
