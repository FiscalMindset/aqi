"""Request bodies for POST routes (kept out of models.py: bodies vs responses)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class SubscriptionRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    locality: str = Field(min_length=2, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    threshold_category: str = Field("Poor")


class AlertPreviewRequest(BaseModel):
    """Render the alert email for a point without sending anything."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    locality: str = Field(default="", max_length=120)
    threshold_category: str = Field(default="Poor", max_length=32)
    causes: list[str] = Field(default_factory=list, max_length=8)
    advice: str | None = Field(default=None, max_length=400)
    unsubscribe_token: str = Field(default="", max_length=64)


class AlertPreviewResponse(BaseModel):
    subject: str
    body: str
    html: str


class RouteSample(BaseModel):
    """One sampled point along a corridor."""

    lat: float
    lon: float
    pm25_mid: float | None
    category: str | None
    data_age_seconds: float | None = None
    served_by: str | None = None


class RouteCorridor(BaseModel):
    """One candidate way through, ranked cleanest first."""

    rank: int
    kind: str  # "road" | "straight-line"
    distance_km: float
    duration_min: float
    mean_pm25: float
    peak_pm25: float
    peak_at: dict[str, float]
    dose_index: float | None
    served_points: int
    geometry: list[list[float]]  # [lon, lat] pairs, GeoJSON order
    samples: list[RouteSample]


class RouteCompareRequest(BaseModel):
    from_lat: float = Field(ge=-90, le=90)
    from_lon: float = Field(ge=-180, le=180)
    to_lat: float = Field(ge=-90, le=90)
    to_lon: float = Field(ge=-180, le=180)
    max_samples: int = Field(default=10, ge=3, le=14)


class RouteCompareResponse(BaseModel):
    origin: dict[str, float]
    destination: dict[str, float]
    router: str
    corridor_count: int
    # Every ranked corridor, cleanest first. A response carrying only
    # cleanest+worst cannot show a ranking, which is the whole feature.
    corridors: list[RouteCorridor] = []
    cleanest: RouteCorridor
    worst: RouteCorridor
    mean_pm25_saving: float
    samples_per_corridor: int
    note: str
    honesty_note: str
