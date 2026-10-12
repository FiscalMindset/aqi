"""Feed orchestration used by routes: fetch -> cache -> last-good.

Every function returns a freshness block alongside the data so routes can
always answer `data_age_seconds` and `stale` honestly. No function here ever
invents a value: when the upstream fails and no cache exists, the caller gets
a typed Problem instead of numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from dhuan.api.deps import (
    get_openaq,
    get_station_cache,
    get_weather,
    get_weather_cache,
)
from dhuan.api.errors import not_configured_problem, upstream_problem
from dhuan.core.config import Settings, get_settings
from dhuan.core.http import UpstreamError
from dhuan.core.logging import get_logger, log_event
from dhuan.core.metrics import record
from dhuan.core.units import Point, haversine_km
from dhuan.ingest.archive import (
    ArchiveUnavailableError,
)
from dhuan.ingest.archive import (
    readings_near as archive_readings_near,
)
from dhuan.ingest.openaq import NotConfiguredError
from dhuan.ingest.types import Reading, WeatherObservation
from dhuan.model.cpcb import category_for_pm25

logger = get_logger("api.services")

STATION_TTL_SECONDS = 900.0
WEATHER_TTL_SECONDS = 1800.0

# Archive readings are as old as the daily files OpenAQ publishes. Beyond this
# we still serve them, but flag them stale so the UI can say so out loud.
ARCHIVE_STALE_AFTER_SECONDS = 36 * 3600.0


@dataclass(slots=True)
class FeedOutcome[T]:
    data: T | None
    age_seconds: float
    stale: bool
    ok: bool
    error: str | None = None


async def stations_near(
    lat: float, lon: float, settings: Settings | None = None
) -> FeedOutcome[list[Reading]]:
    """Latest PM2.5 readings from official stations nearest the point.

    Two real sources, in order of preference:

    1. The OpenAQ v3 API, when a key is configured. Freshest, but needs a
       credential.
    2. The OpenAQ **public archive**, which needs no credential. This is the same
       data the model was trained on, distilled into a compact per-station index.
       An archive reading is as old as the archive, so the age is carried through
       and `stale` is set when it exceeds the threshold.

    If neither source can answer we raise a typed Problem. We never fabricate a
    reading and we never fall back to demo data.
    """
    s = settings or get_settings()
    cache = get_station_cache()
    key = f"stations:{lat:.3f}:{lon:.3f}"

    async def fetch() -> list[Reading]:
        client = get_openaq(s)
        stations = await client.nearby_stations(lat, lon)
        readings: list[Reading] = []
        for st in stations:
            try:
                loc_readings = await client.latest_for_location(int(st.station_id))
                pm25 = [r for r in loc_readings if r.parameter == "pm25"]
                readings.extend(pm25)
            except UpstreamError as exc:
                log_event(logger, 30, "station_fetch_failed", station=st.station_id, error=str(exc))
        # attach station metadata so callers can show names/providers
        by_sensor = {int(s.station_id): s for s in stations}
        enriched: list[Reading] = []
        for r in readings:
            meta = by_sensor.get(int(r.station_id))
            if meta is not None:
                r.name = meta.name
                r.provider = meta.provider
            enriched.append(r)
        return enriched

    if not s.openaq_api_key:
        # No credential: the archive is the real source, not a demo. It is
        # local and cached, so we skip the HTTP cache and record its true age.
        outcome = archive_readings(lat, lon)
        if outcome is not None:
            record("FeedStationsArchiveServed", 1)
            return outcome

    try:
        value, age, stale = await cache.get_or_fetch(key, fetch, ttl_seconds=STATION_TTL_SECONDS)
        record("FeedStationsServed", 1)
        return FeedOutcome(value, age, stale, ok=True)
    except NotConfiguredError as exc:
        record("FeedStationsMissingConfig", 1)
        if archive_readings(lat, lon) is not None:  # pragma: no cover - defensive
            raise
        raise not_configured_problem("OpenAQ") from exc
    except UpstreamError as exc:
        record("FeedStationsFailed", 1)
        # last-good: serve the archive rather than failing the whole request
        fallback = archive_readings(lat, lon)
        if fallback is not None:
            logger.warning("openaq_failed_serving_archive: %s", exc)
            return fallback
        raise upstream_problem("OpenAQ", str(exc)) from exc


def archive_readings(lat: float, lon: float) -> FeedOutcome[list[Reading]] | None:
    """Nearest archive readings with their true age, or None if unavailable."""
    try:
        readings = archive_readings_near(lat, lon)
    except ArchiveUnavailableError as exc:
        logger.warning("archive_unavailable: %s", exc)
        return None
    if not readings:
        return None
    newest = max(r.observed_at for r in readings)
    age = max(0.0, (datetime.now(UTC) - newest).total_seconds())
    return FeedOutcome(
        readings,
        age_seconds=age,
        stale=age > ARCHIVE_STALE_AFTER_SECONDS,
        ok=True,
    )


async def weather_now(
    lat: float, lon: float, settings: Settings | None = None
) -> FeedOutcome[WeatherObservation]:
    s = settings or get_settings()
    cache = get_weather_cache()
    key = f"weather:{lat:.3f}:{lon:.3f}"

    async def fetch() -> WeatherObservation:
        hours = await get_weather(s).forecast(lat, lon, days=1)
        if not hours:
            raise UpstreamError("open-meteo", "no hourly rows returned")
        now = datetime.now(UTC)
        past = [h for h in hours if h.observed_at <= now] or hours
        return past[-1]  # latest observation at/before now

    try:
        value, age, stale = await cache.get_or_fetch(
            key, fetch, ttl_seconds=WEATHER_TTL_SECONDS
        )
        record("FeedWeatherServed", 1)
        return FeedOutcome(value, age, stale, ok=True)
    except UpstreamError as exc:
        record("FeedWeatherFailed", 1)
        raise upstream_problem("Open-Meteo", str(exc)) from exc


async def wind_now(
    lat: float, lon: float, settings: Settings | None = None
) -> FeedOutcome[WeatherObservation]:
    return await weather_now(lat, lon, settings)


def nearest_reading(
    readings: list[Reading], lat: float, lon: float
) -> tuple[Reading, float] | None:
    """Closest reading to the point with its distance (km)."""
    if not readings:
        return None
    target = Point(lat=lat, lon=lon)
    best = min(readings, key=lambda r: haversine_km(target, r.location))
    return best, haversine_km(target, best.location)


def category_of(value: float) -> str:
    return category_for_pm25(value)
