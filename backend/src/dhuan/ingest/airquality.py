"""Open-Meteo air-quality client - an independent second opinion on PM2.5.

Verified against https://open-meteo.com/en/docs/air-quality-api (2026-10-14):
  * `https://air-quality-api.open-meteo.com/v1/air-quality` with `hourly=`,
    `timezone=Asia/Kolkata`, `forecast_days=`. **No key required.**
  * We request `pm2_5`, `pm10`, `dust`, `us_aqi` and `european_aqi`.
  * Values are µg/m³ except the two AQI indices (dimensionless).
  * Data is CAMS (Copernicus Atmosphere Monitoring Service) re-served by
    Open-Meteo.

WHY THIS EXISTS, AND WHAT IT IS NOT
-----------------------------------
It is a *cross-check*, not a second estimate. Our estimate is anchored to a
CPCB ground monitor; this is a regional aerosol model grid. They answer
different questions and routinely disagree, which is precisely why showing both
is useful: a large divergence is a signal that the local station reading and the
regional picture are telling different stories.

It is explicitly NOT a fire source. The API has no fire detection, and the
`dust` variable must never be presented as wildfire smoke. Measured for Delhi on
2026-10-14, `dust` was ~102 µg/m³ during post-monsoon dust season - calling that
"fire smoke" would be a confident fabrication. Fire evidence comes from NASA
FIRMS active-fire detections, which is a genuinely different measurement
(thermal infrared), and is absent when no fire is configured or detected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dhuan.core.config import Settings, get_settings
from dhuan.core.http import HttpPolicy, make_client, make_request
from dhuan.core.logging import get_logger
from dhuan.core.units import Point
from dhuan.ingest.types import AirQualityObservation

logger = get_logger("ingest.airquality")

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

IST = timezone(timedelta(hours=5, minutes=30))

# Kept short on purpose: this is a cross-check on the current hour, not history.
# Open-Meteo publishes no explicit per-minute quota for the keyless air-quality
# endpoint, so the client is deliberately low-frequency and cached upstream.
HOURS = ("pm2_5", "pm10", "dust", "us_aqi", "european_aqi")


def _f(value: float | None) -> float | None:
    return None if value is None else float(value)


def _parse_ist(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=IST)


class AirQualityClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = make_client(HttpPolicy.from_settings(self.settings))

    @property
    def configured(self) -> bool:
        """Always true: this endpoint needs no credential.

        Kept so callers can treat every feed uniformly.
        """
        return True

    async def current(
        self,
        point: Point,
        *,
        forecast_days: int = 1,
    ) -> list[AirQualityObservation]:
        """Hourly CAMS-based aerosol and AQI for the next `forecast_days`.

        Returns rows in chronological order. Rows where every value is missing
        are dropped rather than returned as zeros: absence of data is not a
        reading of zero.
        """
        resp = await make_request(
            self._client,
            HttpPolicy.from_settings(self.settings),
            "open-meteo-air-quality",
            "GET",
            f"{AIR_QUALITY_URL}?latitude={point.lat}&longitude={point.lon}"
            f"&hourly={','.join(HOURS)}&timezone=Asia%2FKolkata"
            f"&forecast_days={max(1, min(forecast_days, 7))}",
        )
        return self._parse(resp.json())

    def _parse(self, payload: dict[str, object]) -> list[AirQualityObservation]:
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            raise TypeError("air-quality response has no hourly block")
        times = hourly.get("time")
        if not isinstance(times, list) or not times:
            return []

        def column(name: str) -> list[float | None]:
            raw = hourly.get(name)
            return list(raw) if isinstance(raw, list) else [None] * len(times)

        cols = {name: column(name) for name in HOURS}
        out: list[AirQualityObservation] = []
        for i, iso in enumerate(times):
            row = {name: _f(cols[name][i] if i < len(cols[name]) else None) for name in HOURS}
            if all(v is None for v in row.values()):
                continue
            out.append(
                AirQualityObservation(
                    observed_at=_parse_ist(str(iso)),
                    pm25=row["pm2_5"],
                    pm10=row["pm10"],
                    dust=row["dust"],
                    us_aqi=row["us_aqi"],
                    european_aqi=row["european_aqi"],
                )
            )
        return out

    async def aclose(self) -> None:
        """Close the current client and leave this instance reusable.

        Clients outlive a single task in a warm Lambda container but cannot
        outlive the event loop they were used on, and a closed client raises
        "Cannot send a request, as the client has been closed" on the next
        task. Rebuilding here keeps the instance safe to reuse.
        """
        await self._client.aclose()
        self._client = make_client(HttpPolicy.from_settings(self.settings))
