"""DEMO_MODE support: serve recorded data with a permanent visible banner.

Rule 1: a `DEMO_MODE=1` environment flag may serve recorded data, but the UI
must show a permanent visible "Demo data" banner whenever it is on, and it
must default to off. This module loads the recorded snapshot from
`fixtures/demo` (never from src) and tags every response with `demo_mode: true`
so the frontend banner and the `X-Dhuan-Demo` response header stay honest.
The recorded data is REAL historical data recorded from the OpenAQ public
archive (see the provenance block inside the file).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.core.units import Point, haversine_km
from dhuan.ingest.types import Reading

logger = get_logger("api.demo")

# Where the recorded snapshot lives. Defaults match the repo layout; the
# container image copies fixtures/demo to /app/demo_data and sets this.
DEMO_DATA_ENV = "DHUAN_DEMO_DATA"


def demo_dir(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    return Path(s.demo_data_dir) if s.demo_data_dir else Path("fixtures/demo")


@lru_cache
def _recordings() -> tuple[dict[str, Any], list[Reading]]:
    path = demo_dir() / "openaq_recorded.json"
    payload = json.loads(path.read_text())
    readings = [
        Reading(
            station_id=str(r["location_id"]),
            name=str(r["location"]),
            location=Point(lat=r["lat"], lon=r["lon"]),
            parameter="pm25",
            value=float(r["value"]),
            unit=r["units"],
            observed_at=datetime.fromisoformat(r["datetime"]).replace(tzinfo=UTC),
            provider="recorded-openaq-archive",
        )
        for r in payload["readings"]
    ]
    return payload.get("provenance", {}), readings


def recorded_provenance() -> dict[str, Any]:
    return dict(_recordings()[0])


def recorded_readings() -> list[Reading]:
    return list(_recordings()[1])


def latest_recorded_reading() -> Reading | None:
    readings = recorded_readings()
    if not readings:
        return None
    return max(readings, key=lambda r: r.observed_at)


def stations_near_demo(lat: float, lon: float) -> list[Reading]:
    """Most recent recorded readings nearest the requested point."""
    target = Point(lat=lat, lon=lon)
    return sorted(recorded_readings(), key=lambda r: haversine_km(target, r.location))[:10]


def demo_age_seconds() -> float:
    latest = latest_recorded_reading()
    if latest is None:
        return 0.0
    return (datetime.now(UTC) - latest.observed_at).total_seconds()
