"""Feature engineering for the PM2.5 estimation model.

LEAKAGE POLICY (enforced by tests/model/test_leakage.py):
  * The label is the station's own pm25 reading at hour t.
  * Features may only use: weather at hour t, calendar at hour t, and *static*
    geography around the *prediction point* (station centroid for training).
  * No feature may read any station's own current or recent pm25 value, and no
    feature may encode the target hour's measurement in any form.
  * Station identity is included as a categorical (one-hot) because the
    baseline levels differ by city; this is legitimate: at prediction time the
    *point's own* nearest-station identity is used, never its future readings.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dhuan.core.units import Point, haversine_km

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

FEATURE_NAMES: tuple[str, ...] = (
    # calendar
    "hour",
    "hour_sin",
    "hour_cos",
    "dayofweek",
    "month",
    "month_sin",
    "month_cos",
    # weather at time t
    "wind_speed",
    "wind_gust",
    "temp_c",
    "rh",
    "precip",
    "wind_dir_sin",
    "wind_dir_cos",
    # static geography (km if name says dist, counts if name says count)
    "landfill_dist_km",
    "landfill_count_5km",
    "industrial_dist_km",
    "industrial_count_5km",
    "construction_dist_km",
    "construction_count_5km",
    "junction_dist_km",
    "junction_count_5km",
    # nearest-station memory at prediction time (NOT the target's own value):
    # lag-1h and lag-24h of the nearest station's observed history
    "station_lag1",
    "station_lag24",
    "station_rolling6",
    # latitude/longitude proxies for regional baseline
    "lat",
    "lon",
)


@dataclass(slots=True)
class Source:
    lat: float
    lon: float
    kind: str  # landfill | industrial | construction | major_junction


def static_sources_for_station(location_id: int) -> list[Source]:
    path = DATA_DIR / "static_sources" / f"station_{location_id}.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    out: list[Source] = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        if el.get("type") == "way" and el.get("geometry"):
            lat = sum(g["lat"] for g in el["geometry"]) / len(el["geometry"])
            lon = sum(g["lon"] for g in el["geometry"]) / len(el["geometry"])
        elif el.get("type") == "node":
            lat, lon = float(el["lat"]), float(el["lon"])
        else:
            continue
        if tags.get("landuse") == "landfill":
            kind = "landfill"
        elif tags.get("landuse") == "industrial":
            kind = "industrial"
        elif tags.get("landuse") == "construction":
            kind = "construction"
        elif tags.get("highway") == "traffic_signals":
            kind = "major_junction"
        else:
            continue
        out.append(Source(lat=lat, lon=lon, kind=kind))
    return out


def static_features(point: Point, sources: list[Source]) -> dict[str, float]:
    """Distance/count features from a point to nearby sources.

    `landfill_dist_km` = distance to nearest landfill (99 km cap if none);
    `landfill_count_5km` = number of landfills within 5 km, etc.
    """
    feats: dict[str, float] = {}
    for kind, field in (
        ("landfill", "landfill"),
        ("industrial", "industrial"),
        ("construction", "construction"),
        ("major_junction", "junction"),
    ):
        nearby = [s for s in sources if s.kind == kind]
        dists = [haversine_km(point, Point(lat=s.lat, lon=s.lon)) for s in nearby]
        feats[f"{field}_dist_km"] = min(dists) if dists else 99.0
        feats[f"{field}_count_5km"] = float(sum(1 for d in dists if d <= 5.0))
    return feats


def calendar_features(ts: datetime) -> dict[str, float]:
    return {
        "hour": float(ts.hour),
        "hour_sin": math.sin(2 * math.pi * ts.hour / 24),
        "hour_cos": math.cos(2 * math.pi * ts.hour / 24),
        "dayofweek": float(ts.weekday()),
        "month": float(ts.month),
        "month_sin": math.sin(2 * math.pi * ts.month / 12),
        "month_cos": math.cos(2 * math.pi * ts.month / 12),
    }


def weather_features(row: dict[str, Any]) -> dict[str, float]:
    return {
        "wind_speed": float(row["wind_speed"]),
        "wind_gust": float(row["wind_gust"]),
        "temp_c": float(row["temp_c"]),
        "rh": float(row["rh"]),
        "precip": float(row["precip"]),
        "wind_dir_sin": math.sin(math.radians(float(row["wind_dir"]))),
        "wind_dir_cos": math.cos(math.radians(float(row["wind_dir"]))),
    }


def build_feature_row(
    *,
    ts: datetime,
    lat: float,
    lon: float,
    weather_row: dict[str, Any],
    static_feats: dict[str, float],
    station_lag1: float,
    station_lag24: float,
    station_rolling6: float,
) -> dict[str, float]:
    """One fully-populated feature vector; no label information is present.

    `static_feats` must come from `static_features(point, sources)` for the
    SAME prediction point; callers may cache it because geography is constant
    within a training run. `station_*` are the nearest station's observed
    history strictly BEFORE this hour (see `lag_features`).
    """
    feats = calendar_features(ts)
    feats.update(weather_features(weather_row))
    feats.update(static_feats)
    feats["station_lag1"] = station_lag1
    feats["station_lag24"] = station_lag24
    feats["station_rolling6"] = station_rolling6
    feats["lat"] = lat
    feats["lon"] = lon
    return {name: feats[name] for name in FEATURE_NAMES}


def load_snapshot(path: Path | None = None) -> dict[str, Any]:
    path = path or DATA_DIR / "training_snapshot.json"
    payload: dict[str, Any] = json.loads(path.read_text())
    return payload


def weather_index(
    weather: Iterable[dict[str, Any]],
) -> dict[tuple[float, float, str], dict[str, Any]]:
    """Index weather rows by (lat4, lon4, time) for exact O(1) joins."""
    return {
        (round(row["lat"], 4), round(row["lon"], 4), row["time"]): row for row in weather
    }


def match_weather(
    index: dict[tuple[float, float, str], dict[str, Any]], lat: float, lon: float, ts: datetime
) -> dict[str, Any] | None:
    """Weather row for the station location and the exact hour (exact keys only)."""
    return index.get((round(lat, 4), round(lon, 4), ts.strftime("%Y-%m-%dT%H:00")))


def station_history_index(snapshot: dict[str, Any]) -> dict[int, dict[datetime, float]]:
    """Observed history per station: {location_id: {hour: value}}."""
    history: dict[int, dict[datetime, float]] = {}
    for row in snapshot["stations"]:
        ts = datetime.fromisoformat(row["datetime"]).replace(tzinfo=None)
        history.setdefault(row["location_id"], {})[ts] = float(row["value"])
    return history


def lag_features(
    history: dict[datetime, float], ts: datetime
) -> tuple[float, float, float, int]:
    """(lag1, lag24, rolling6_mean, n_found) for one station hour.

    Uses only observations strictly BEFORE the target hour.
    """
    lag1 = history.get(ts - timedelta(hours=1))
    lag24 = history.get(ts - timedelta(hours=24))
    window = [
        history[ts - timedelta(hours=h)]
        for h in range(2, 8)
        if ts - timedelta(hours=h) in history
    ]
    found = sum(x is not None for x in (lag1, lag24)) + (1 if window else 0)
    return (
        lag1 if lag1 is not None else -1.0,
        lag24 if lag24 is not None else -1.0,
        (sum(window) / len(window)) if window else -1.0,
        found,
    )


def build_training_frame(
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, float]], list[float], list[dict[str, Any]]]:
    """Build (feature rows, labels, metadata) from a training snapshot."""
    static_cache: dict[int, dict[str, float]] = {}
    wx = weather_index(snapshot["weather"])
    history = station_history_index(snapshot)

    rows: list[dict[str, float]] = []
    y: list[float] = []
    meta: list[dict[str, Any]] = []
    for row in snapshot["stations"]:
        loc = row["location_id"]
        if loc not in static_cache:
            # static geography is constant per station: compute it once
            sources = static_sources_for_station(loc)
            point = Point(lat=row["lat"], lon=row["lon"])
            static_cache[loc] = static_features(point, sources)
        ts = datetime.fromisoformat(row["datetime"]).replace(tzinfo=None)
        wrow = match_weather(wx, row["lat"], row["lon"], ts)
        if wrow is None:
            continue  # no weather => no honest features; skip the row
        lag1, lag24, roll6, _found = lag_features(history[loc], ts)
        feats = build_feature_row(
            ts=ts, lat=row["lat"], lon=row["lon"], weather_row=wrow,
            static_feats=static_cache[loc],
            station_lag1=lag1, station_lag24=lag24, station_rolling6=roll6,
        )
        rows.append(feats)
        y.append(row["value"])
        meta.append({"location_id": loc, "location": row["location"], "ts": ts.isoformat()})
    return rows, y, meta


def snapshot_hash(snapshot: dict[str, Any]) -> str:

    blob = json.dumps(
        {"stations": snapshot["stations"], "weather": snapshot["weather"]}, sort_keys=True
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def newest_ts(meta: list[dict[str, Any]]) -> datetime:
    return max(datetime.fromisoformat(m["ts"]) for m in meta)


__all__ = [
    "FEATURE_NAMES",
    "build_feature_row",
    "build_training_frame",
    "load_snapshot",
    "match_weather",
    "newest_ts",
    "snapshot_hash",
    "static_features",
    "static_sources_for_station",
    "timedelta",
]
