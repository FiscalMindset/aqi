"""Open-Meteo weather client.

Verified against https://open-meteo.com/docs (2026-10-15):
  * Forecast: `https://api.open-meteo.com/v1/forecast` with `hourly=`,
    `wind_speed_unit=ms`, `timezone=Asia/Kolkata`. No key required.
  * Historical archive: `https://archive-api.open-meteo.com/v1/archive`.
  * Hourly variables used here: `wind_speed_10m`, `wind_direction_10m`,
    `wind_gusts_10m`, `temperature_2m`, `relative_humidity_2m`,
    `precipitation`. Wind direction is the meteorological "wind FROM" bearing
    in degrees, which is exactly what our upwind cone expects.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dhuan.core.config import Settings, get_settings
from dhuan.core.http import HttpPolicy, make_client, make_request
from dhuan.core.logging import get_logger
from dhuan.core.units import Point
from dhuan.ingest.types import WeatherObservation

logger = get_logger("ingest.weather")

# India Standard Time is a fixed +05:30 offset (no DST); Open-Meteo returns
# local ISO timestamps when a timezone is requested.
IST = timezone(timedelta(hours=5, minutes=30))


def _opt_float(value: float | None, default: float | None = None) -> float | None:
    if value is None:
        return default
    return float(value)


def _req_float(value: float | None, default: float) -> float:
    return default if value is None else float(value)


def _parse_ist(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt

HOURLY_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
]


class WeatherClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = make_client(HttpPolicy.from_settings(self.settings))

    async def _hourly(
        self, base_url: str, lat: float, lon: float, extra: dict[str, str]
    ) -> list[WeatherObservation]:
        params = {
            "latitude": str(lat),
            "longitude": str(lon),
            "hourly": ",".join(HOURLY_VARS),
            "timezone": "Asia/Kolkata",
            "wind_speed_unit": "ms",
            **extra,
        }
        resp = await make_request(
            self._client,
            HttpPolicy.from_settings(self.settings),
            "open-meteo",
            "GET",
            base_url,
            params=params,
        )
        payload = resp.json()
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            return []
        n = len(times)

        def col(name: str) -> list[float | None]:
            return hourly.get(name) or [None] * n

        wind_ms = col("wind_speed_10m")
        wind_dir = col("wind_direction_10m")
        gusts = col("wind_gusts_10m")
        temp = col("temperature_2m")
        rh = col("relative_humidity_2m")
        precip = col("precipitation")

        out: list[WeatherObservation] = []
        for i, iso in enumerate(times):
            ws = wind_ms[i]
            wd = wind_dir[i]
            if ws is None or wd is None:
                continue  # missing wind => cannot attribute; skip the hour
            out.append(
                WeatherObservation(
                    location=Point(lat=lat, lon=lon),
                    observed_at=_parse_ist(iso),
                    wind_speed_ms=float(ws),
                    wind_direction_deg=float(wd),
                    wind_gusts_ms=_opt_float(gusts[i]),
                    temperature_c=_req_float(temp[i], 0.0),
                    relative_humidity_pct=_req_float(rh[i], 0.0),
                    precipitation_mm=_req_float(precip[i], 0.0),
                )
            )
        return out

    async def forecast(self, lat: float, lon: float, days: int = 2) -> list[WeatherObservation]:
        return await self._hourly(
            f"{self.settings.openmeteo_base_url}/v1/forecast",
            lat,
            lon,
            {"forecast_days": str(days)},
        )

    async def historical(
        self, lat: float, lon: float, start: str, end: str
    ) -> list[WeatherObservation]:
        """Hourly archive between inclusive ISO dates (archive API host)."""
        archive_url = "https://archive-api.open-meteo.com/v1/archive"
        return await self._hourly(archive_url, lat, lon, {"start_date": start, "end_date": end})

    async def latest(self, lat: float, lon: float) -> WeatherObservation | None:
        """Most recent hour available from the forecast feed."""
        hours = await self.forecast(lat, lon, days=1)
        return hours[0] if hours else None

    async def aclose(self) -> None:
        """Close the current client and leave this instance reusable.

        These clients are cached process-wide in api/deps.py, and a Lambda
        container handles many invocations. Closing the client without
        replacing it left the cache holding a closed httpx client, so the next
        invocation raised "Cannot send a request, as the client has been
        closed" and the task silently degraded to a branch failure. Each
        invocation also runs its own event loop, so a client bound to a
        finished loop cannot be reused anyway - rebuild it here.
        """
        await self._client.aclose()
        self._client = make_client(HttpPolicy.from_settings(self.settings))


def latest_complete(observations: list[WeatherObservation]) -> WeatherObservation | None:
    return observations[0] if observations else None
