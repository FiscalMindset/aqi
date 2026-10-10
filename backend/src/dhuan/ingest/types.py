"""Shared ingest types used by every feed client.

Every reading carries provenance (source + observed time) so the API can
always report `data_age_seconds` and the UI can show freshness honestly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from dhuan.core.units import Point


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Station:
    """A monitoring station as reported by OpenAQ v3."""

    station_id: str
    name: str
    location: Point
    provider: str
    pm25_sensor_id: int | None = None
    last_reading_at: datetime | None = None
    country_code: str = "IN"


@dataclass(slots=True)
class Reading:
    """One PM2.5 measurement from a station."""

    station_id: str
    name: str
    location: Point
    parameter: str
    value: float
    unit: str
    observed_at: datetime
    provider: str
    license_note: str = "OpenAQ (CC BY 4.0)"

    def age_seconds(self) -> float:
        # clamped at 0: provider clocks can run slightly ahead; a negative
        # age is meaningless and must never be shown
        return max(0.0, (utcnow() - self.observed_at).total_seconds())


@dataclass(slots=True)
class WeatherObservation:
    """Hourly weather at a point (Open-Meteo)."""

    location: Point
    observed_at: datetime
    wind_speed_ms: float
    wind_direction_deg: float
    wind_gusts_ms: float | None
    temperature_c: float
    relative_humidity_pct: float
    precipitation_mm: float = 0.0


@dataclass(slots=True)
class FireDetection:
    """A NASA FIRMS active-fire detection."""

    latitude: float
    longitude: float
    brightness_k: float
    acq_datetime: datetime
    confidence: str
    source: str


@dataclass(slots=True)
class FeedStatus:
    """Per-feed freshness record (surfaced verbatim by /v1/status)."""

    feed: str
    ok: bool
    last_success_at: datetime | None
    last_error: str | None = None
    records_last_run: int = 0

    def age_seconds(self) -> float | None:
        if self.last_success_at is None:
            return None
        return (utcnow() - self.last_success_at).total_seconds()


@dataclass(slots=True)
class FeedResult[T]:
    """A feed response plus the freshness of what produced it."""

    value: T
    feed: str
    fetched_at: datetime = field(default_factory=utcnow)
    stale: bool = False
    age_seconds: float = 0.0
