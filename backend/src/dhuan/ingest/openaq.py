"""OpenAQ v3 API client.

Verified against https://docs.openaq.org (2026-10-15):
  * Auth header: `X-API-Key` (free tier 60 req/min, 2 000 req/hour).
  * `GET /v3/locations?coordinates=<lat>,<lon>&radius=<m>&limit=<n>` for station
    discovery (max radius 25 000 m).
  * `GET /v3/locations/{id}/latest` for latest readings per sensor.
  * `GET /v3/sensors/{id}/hours` for hourly averages (training history).
  * v1/v2 endpoints were retired on 2025-01-31 and return HTTP 410.

Without an API key the client refuses to fabricate data: it raises
`NotConfiguredError`, which the API surfaces as an unavailable feed in
`/v1/status` (honesty rule). With no key the caller falls back to the
credential-free public archive in `ingest/archive.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from dhuan.core.config import Settings, get_settings
from dhuan.core.http import HttpPolicy, UpstreamClient, UpstreamError, make_client, make_request
from dhuan.core.logging import get_logger, log_event
from dhuan.core.units import Point
from dhuan.ingest.types import Reading, Station, utcnow

logger = get_logger("ingest.openaq")

BASE_URL = "https://api.openaq.org/v3"
MAX_RADIUS_M = 25_000


class NotConfiguredError(RuntimeError):
    """Raised when a required credential is missing."""


class OpenAQClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = make_client(HttpPolicy.from_settings(self.settings))

    @property
    def configured(self) -> bool:
        return bool(self.settings.openaq_api_key)

    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise NotConfiguredError(
                "OPENAQ_API_KEY is not set; station data unavailable (no fabricated fallback)"
            )
        return {"X-API-Key": self.settings.openaq_api_key}

    async def nearby_stations(
        self, lat: float, lon: float, radius_m: int = 25_000, limit: int = 100
    ) -> list[Station]:
        radius_m = min(radius_m, MAX_RADIUS_M)
        resp = await make_request(
            self._client,
            HttpPolicy.from_settings(self.settings),
            "openaq",
            "GET",
            f"{BASE_URL}/locations",
            params={
                "coordinates": f"{lat},{lon}",
                "radius": radius_m,
                "limit": limit,
                "iso": "IN",
            },
            headers=self._headers(),
        )
        payload = resp.json()
        stations: list[Station] = []
        for item in payload.get("results", []):
            sensors = item.get("sensors") or []
            pm25 = next(
                (s for s in sensors if s.get("parameter", {}).get("name") == "pm25"), None
            )
            coords = item.get("coordinates") or {}
            last = item.get("datetimeLast") or {}
            last_utc = last.get("utc")
            stations.append(
                Station(
                    station_id=str(item.get("id")),
                    name=item.get("name", "unknown"),
                    location=Point(lat=coords["latitude"], lon=coords["longitude"]),
                    provider=(item.get("provider") or {}).get("name", "unknown"),
                    pm25_sensor_id=int(pm25["id"]) if pm25 else None,
                    last_reading_at=_parse_ts(last_utc),
                )
            )
        log_event(
            logger, 20, "openaq_stations_fetched",
            count=len(stations), lat=lat, lon=lon, radius=radius_m,
        )
        return stations

    async def latest_for_location(self, location_id: int) -> list[Reading]:
        resp = await make_request(
            self._client,
            HttpPolicy.from_settings(self.settings),
            "openaq",
            "GET",
            f"{BASE_URL}/locations/{location_id}/latest",
            headers=self._headers(),
        )
        payload = resp.json()
        return _parse_latest(payload)

    async def hourly_history(self, sensor_id: int, date_from: str, date_to: str) -> list[Reading]:
        """Hourly averages for one sensor between ISO dates (training data)."""
        resp = await make_request(
            self._client,
            HttpPolicy.from_settings(self.settings),
            "openaq",
            "GET",
            f"{BASE_URL}/sensors/{sensor_id}/hours",
            params={"date_from": date_from, "date_to": date_to, "limit": 1000},
            headers=self._headers(),
        )
        results = resp.json().get("results", [])
        readings: list[Reading] = []
        for item in results:
            coords = item.get("coordinates") or {}
            dt = _parse_ts((item.get("datetime") or {}).get("utc") or item.get("datetime"))
            if dt is None or not coords:
                continue
            readings.append(
                Reading(
                    station_id=str(sensor_id),
                    name=item.get("location") or str(sensor_id),
                    location=Point(lat=coords["latitude"], lon=coords["longitude"]),
                    parameter=item.get("parameter") or "pm25",
                    value=float(item["value"]),
                    unit=item.get("unit", "µg/m³"),
                    observed_at=dt,
                    provider="openaq",
                )
            )
        return readings

    async def aclose(self) -> None:
        await self._client.aclose()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _parse_latest(payload: dict[str, Any]) -> list[Reading]:
    readings: list[Reading] = []
    for item in payload.get("results", []):
        coords = item.get("coordinates") or {}
        dt = _parse_ts((item.get("datetime") or {}).get("utc"))
        if dt is None or not coords:
            continue
        value = item.get("value")
        if value is None:
            continue
        readings.append(
            Reading(
                station_id=str(item.get("sensorsId")),
                name=str(item.get("locationsId")),
                location=Point(lat=coords["latitude"], lon=coords["longitude"]),
                parameter="pm25",
                value=float(value),
                unit="µg/m³",
                observed_at=dt,
                provider="openaq",
            )
        )
    return readings


async def fetch_nearby_readings(
    lat: float, lon: float, settings: Settings | None = None
) -> list[Reading]:
    """Convenience: stations near a point, then their latest PM2.5 readings."""
    client = OpenAQClient(settings)
    try:
        stations = await client.nearby_stations(lat, lon)
        readings: list[Reading] = []
        for station in stations:
            if station.pm25_sensor_id is None:
                continue
            try:
                readings.extend(await client.latest_for_location(int(station.station_id)))
            except UpstreamError as exc:
                log_event(
                    logger, 30, "openaq_station_failed",
                    station=station.station_id, error=str(exc),
                )
        return readings
    finally:
        await client.aclose()


__all__ = [
    "NotConfiguredError",
    "OpenAQClient",
    "UpstreamClient",
    "fetch_nearby_readings",
    "utcnow",
]
