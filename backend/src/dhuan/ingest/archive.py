"""Serve real station readings from the OpenAQ public archive, with no API key.

The OpenAQ v3 API needs a credential. The public archive does not: it is a set
of daily CSV/JSON files on the OpenAQ S3 bucket, and it is where the training
snapshot already came from. This module turns those files into the same
`Reading` objects the API serves, so the product works on real data with no
credential and no demo mode.

Design decisions:

- **Real, not synthetic.** Every value came from an OpenAQ archive file. If the
  archive is unreachable we say so; we never fabricate a reading.
- **Explicit freshness.** An archive reading is as old as the archive. The age is
  carried through to the API response so the UI can show how stale it is, and
  `stale` is set when it exceeds the configured threshold.
- **Cached in memory.** The index is a few hundred KB; it is loaded once per
  container and reused.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from dhuan.core.logging import get_logger
from dhuan.core.units import Point, haversine_km
from dhuan.ingest.types import Reading

logger = get_logger("ingest.archive")

# The compact per-station index built by scripts/build_station_index.py from the
# archive snapshot. It is the same data the model trained on.
DEFAULT_INDEX = Path(__file__).resolve().parents[3] / "data" / "station_index.json"

INDEX_ENV = "DHUAN_STATION_INDEX"

# Beyond this the reading is served but flagged stale.
DEFAULT_STALE_AFTER_SECONDS = 36 * 3600.0


class ArchiveUnavailableError(RuntimeError):
    """The archive index is missing or unreadable."""


def index_path() -> Path:
    override = os.environ.get(INDEX_ENV)
    return Path(override) if override else DEFAULT_INDEX


@lru_cache(maxsize=1)
def load_index() -> dict[str, Any]:
    path = index_path()
    if not path.exists():
        raise ArchiveUnavailableError(
            f"station archive index not found at {path}; "
            "run scripts/build_station_index.py or set DHUAN_STATION_INDEX"
        )
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ArchiveUnavailableError(f"station archive index unreadable: {exc}") from exc
    if not isinstance(data.get("stations"), list):
        raise ArchiveUnavailableError("station archive index has no stations")
    return data


def archive_provenance() -> dict[str, Any]:
    data = load_index()
    provenance = data.get("provenance", {})
    return dict(provenance) if isinstance(provenance, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _station_entries() -> list[dict[str, Any]]:
    data = load_index()
    entries: list[dict[str, Any]] = []
    for station in data.get("stations", []):
        if not isinstance(station, dict):
            continue
        latest = station.get("latest")
        if not isinstance(latest, dict):
            continue
        observed = _parse_ts(latest.get("t"))
        if observed is None:
            continue
        try:
            lat = float(station["lat"])
            lon = float(station["lon"])
            value = float(latest["v"])
        except (KeyError, TypeError, ValueError):
            continue
        entries.append(
            {
                "location_id": str(station.get("location_id", "")),
                "sensor_id": station.get("sensor_id"),
                "name": station.get("name") or "unnamed station",
                "lat": lat,
                "lon": lon,
                "value": value,
                "observed_at": observed,
                "history": station.get("history") or [],
            }
        )
    return entries


@lru_cache(maxsize=1)
def _all_readings() -> tuple[Reading, ...]:
    readings: list[Reading] = []
    for entry in _station_entries():
        for point in entry["history"]:
            observed = _parse_ts(point.get("t"))
            if observed is None:
                continue
            try:
                value = float(point["v"])
            except (KeyError, TypeError, ValueError):
                continue
            readings.append(
                Reading(
                    station_id=entry["location_id"],
                    name=str(entry["name"]),
                    location=Point(lat=entry["lat"], lon=entry["lon"]),
                    parameter="pm25",
                    value=value,
                    unit="µg/m³",
                    observed_at=observed,
                    provider="openaq-public-archive",
                )
            )
    return tuple(readings)


def readings_near(
    lat: float,
    lon: float,
    *,
    radius_km: float = 25.0,
    limit: int = 5,
    as_of: datetime | None = None,
) -> list[Reading]:
    """Latest reading per archive station within `radius_km`, nearest first.

    One reading per station: the caller wants "what is the nearest official
    monitor saying now", not the station's whole history.
    """
    centre = Point(lat=lat, lon=lon)
    now = as_of or datetime.now(UTC)
    latest: dict[str, tuple[float, Reading]] = {}

    for reading in _all_readings():
        distance = haversine_km(centre, reading.location)
        if distance > radius_km:
            continue
        if reading.observed_at > now:
            continue  # never serve a reading from the future
        current = latest.get(reading.station_id)
        if current is None or reading.observed_at > current[1].observed_at:
            latest[reading.station_id] = (distance, reading)

    ordered = sorted(latest.values(), key=lambda pair: pair[0])
    return [reading for _, reading in ordered[:limit]]


def newest_observation() -> datetime | None:
    """The most recent observation anywhere in the archive."""
    readings = _all_readings()
    if not readings:
        return None
    return max(r.observed_at for r in readings)


def archive_age_seconds(as_of: datetime | None = None) -> float:
    newest = newest_observation()
    if newest is None:
        return 0.0
    now = as_of or datetime.now(UTC)
    return max(0.0, (now - newest).total_seconds())


def is_stale(as_of: datetime | None = None, threshold: float | None = None) -> bool:
    limit = threshold if threshold is not None else DEFAULT_STALE_AFTER_SECONDS
    return archive_age_seconds(as_of) > limit


def parse_archive_csv(text: str) -> list[dict[str, Any]]:
    """Parse one OpenAQ archive CSV into normalised rows.

    Used by the scheduled refresh task, which downloads the newest daily files
    and folds them into the index. Kept here so the parsing rules live next to
    the reader that consumes them.
    """
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        parameter = (raw.get("parameter") or raw.get("parameterid") or "").lower()
        if "pm25" not in parameter:
            continue
        try:
            value = float(raw.get("value", ""))
            lat = float(raw.get("latitude", ""))
            lon = float(raw.get("longitude", ""))
        except (TypeError, ValueError):
            continue
        stamp = (
            raw.get("datetime")
            or raw.get("datetimeutc")
            or raw.get("lastupdated")
            or raw.get("utc")
        )
        observed = _parse_ts(stamp) if stamp else None
        if observed is None:
            continue
        rows.append(
            {
                "location_id": str(raw.get("locationid") or raw.get("location_id") or ""),
                "sensor_id": raw.get("sensorid") or raw.get("sensor_id"),
                "name": raw.get("location") or raw.get("locationname") or "unnamed station",
                "lat": lat,
                "lon": lon,
                "value": value,
                "t": observed.isoformat(),
            }
        )
    return rows


def maybe_decompress(payload: bytes) -> str:
    """Archive files are served gzipped by content-encoding; handle both."""
    if payload[:2] == b"\x1f\x8b":
        return gzip.decompress(payload).decode("utf-8")
    return payload.decode("utf-8")


__all__ = [
    "INDEX_ENV",
    "ArchiveUnavailableError",
    "archive_age_seconds",
    "archive_provenance",
    "is_stale",
    "load_index",
    "maybe_decompress",
    "newest_observation",
    "parse_archive_csv",
    "readings_near",
]
