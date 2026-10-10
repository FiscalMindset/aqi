"""NASA FIRMS active-fire client.

Verified against https://firms.modaps.eosdis.nasa.gov/api/area/ (2026-10-15):
  * `GET /api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}`
    with `DAY_RANGE` 1..5 and `SOURCE` in {VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT,
    VIIRS_NOAA21_NRT, MODIS_NRT, ...}. Area is a bbox `west,south,east,north`.
  * CSV columns: latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,
    satellite,instrument,confidence,version,bright_ti5,frp,daynight.
  * Free MAP_KEY, 5 000 transactions per 10-minute interval.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from dhuan.core.config import Settings, get_settings
from dhuan.core.http import HttpPolicy, make_client, make_request
from dhuan.core.logging import get_logger
from dhuan.core.units import Point, haversine_km
from dhuan.ingest.openaq import NotConfiguredError
from dhuan.ingest.types import FireDetection

logger = get_logger("ingest.firms")

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
DEFAULT_SOURCE = "VIIRS_SNPP_NRT"


class FireClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = make_client(HttpPolicy.from_settings(self.settings))

    @property
    def configured(self) -> bool:
        return bool(self.settings.firms_map_key)

    async def fires_in_bbox(  # noqa: PLR0917 - bbox params stay positional for readability
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        day_range: int = 1,
        source: str = DEFAULT_SOURCE,
    ) -> list[FireDetection]:
        if not self.configured:
            raise NotConfiguredError("FIRMS_MAP_KEY is not set; fire feed unavailable")
        day_range = max(1, min(day_range, 5))
        area = f"{west},{south},{east},{north}"
        resp = await make_request(
            self._client,
            HttpPolicy.from_settings(self.settings),
            "firms",
            "GET",
            f"{BASE_URL}/{self.settings.firms_map_key}/{source}/{area}/{day_range}",
        )
        return self._parse_csv(resp.text, source)

    def _parse_csv(self, text: str, source: str) -> list[FireDetection]:
        if not text.strip():
            return []
        reader = csv.DictReader(io.StringIO(text))
        out: list[FireDetection] = []
        for row in reader:
            try:
                acq_date = row["acq_date"]
                acq_time = row["acq_time"]
                dt = datetime.strptime(f"{acq_date} {acq_time}", "%Y-%m-%d %H%M").replace(
                    tzinfo=UTC
                )
                out.append(
                    FireDetection(
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        brightness_k=float(row.get("bright_ti4") or 0.0),
                        acq_datetime=dt,
                        confidence=str(row.get("confidence", "")),
                        source=source,
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("firms_row_skipped: %s", exc)
                continue
        return out

    async def recent_in_ncr(self, day_range: int = 3) -> list[FireDetection]:
        """Fires in a bbox around Delhi-NCR (includes upwind Punjab/Haryana)."""
        return await self.fires_in_bbox(
            west=75.8, south=27.5, east=78.5, north=30.5, day_range=day_range
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def count_recent(
    fires: list[FireDetection], since: datetime, lat: float, lon: float, radius_km: float
) -> int:
    """Count detections newer than `since` within a radius (haversine)."""
    center = Point(lat=lat, lon=lon)
    cutoff = since if since.tzinfo else since.replace(tzinfo=UTC)
    n = 0
    for f in fires:
        if f.acq_datetime < cutoff:
            continue
        if haversine_km(center, Point(lat=f.latitude, lon=f.longitude)) <= radius_km:
            n += 1
    return n


__all__ = ["FireClient", "NotConfiguredError", "count_recent"]
