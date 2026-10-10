"""Fetch real station history + weather to build the training dataset.

Data sources (all verified, see docs/DATA_SOURCES.md):
  * OpenAQ public archive bucket (no credentials): per-location daily CSV.gz.
  * Open-Meteo archive API (no key): hourly weather at each station.

Only stations with hourly pm25 inside India are used. The output parquet
records the snapshot hash so `make train` is reproducible.
"""

from __future__ import annotations

import concurrent.futures
import csv
import gzip
import hashlib
import io
import json
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ARCHIVE = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz"
WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"

OUT = Path(__file__).resolve().parents[1] / "backend" / "data"
STATIONS = {
    8118: (28.63576, 77.22445),  # New Delhi
    931708: (13.08784, 80.278475),  # Chennai
    8557: (17.38405, 78.45636),  # Hyderabad
    8039: (19.07283, 72.88261),  # Mumbai
}
START = "2023-06-01"
END = "2023-12-31"


def _http_get(url: str, data: bytes | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(
        url, data=data, headers={"User-Agent": "DhuanDetective/1.0 (contact: team@dhuan-detective.example)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URLs
        return resp.read()


def fetch_station_day(loc: int, day: str) -> list[dict[str, Any]]:
    url = f"{ARCHIVE}/locationid={loc}/year={day[:4]}/month={day[4:6]}/location-{loc}-{day}.csv.gz"
    try:
        text = gzip.decompress(_http_get(url)).decode()
    except Exception:  # noqa: BLE001 - missing days are expected
        return []
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("parameter") != "pm25":
            continue
        rows.append(
            {
                "location_id": int(r["location_id"]),
                "sensor_id": int(r["sensors_id"]),
                "location": r["location"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "datetime": r["datetime"],
                "value": float(r["value"]),
            }
        )
    return rows


def fetch_weather(lat: float, lon: float, start: str, end: str) -> list[dict[str, Any]]:
    params = (
        f"latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
        "&hourly=temperature_2m,relative_humidity_2m,precipitation,"
        "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        "&timezone=Asia%2FKolkata&wind_speed_unit=ms"
    )
    payload = json.loads(_http_get(f"{WEATHER_API}?{params}"))
    hourly = payload["hourly"]
    n = len(hourly["time"])
    out = []
    for i in range(n):
        ws, wd = hourly["wind_speed_10m"][i], hourly["wind_direction_10m"][i]
        if ws is None or wd is None:
            continue
        out.append(
            {
                "lat": lat,
                "lon": lon,
                "time": hourly["time"][i],
                "temp_c": hourly["temperature_2m"][i],
                "rh": hourly["relative_humidity_2m"][i],
                "precip": hourly["precipitation"][i] or 0.0,
                "wind_speed": ws,
                "wind_dir": wd,
                "wind_gust": hourly["wind_gusts_10m"][i] or 0.0,
            }
        )
    return out


def daterange(start: str, end: str) -> list[str]:
    d0 = datetime.strptime(start, "%Y-%m-%d")
    d1 = datetime.strptime(end, "%Y-%m-%d")
    return [(d0 + timedelta(days=i)).strftime("%Y%m%d") for i in range((d1 - d0).days + 1)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    days = daterange(START, END)
    station_rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(fetch_station_day, loc, day): (loc, day) for loc in STATIONS for day in days}
        for fut in concurrent.futures.as_completed(futures):
            station_rows.extend(fut.result())
    print(f"station rows: {len(station_rows)}", file=sys.stderr)

    weather_rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(fetch_weather, lat, lon, START, END): loc for loc, (lat, lon) in STATIONS.items()
        }
        for fut in concurrent.futures.as_completed(futures):
            weather_rows.extend(fut.result())
    print(f"weather rows: {len(weather_rows)}", file=sys.stderr)

    blob = json.dumps({"stations": station_rows, "weather": weather_rows}, sort_keys=True)
    digest = hashlib.sha256(blob.encode()).hexdigest()
    payload = {
        "provenance": {
            "sources": {
                "stations": "OpenAQ public archive bucket (no credentials)",
                "weather": "Open-Meteo archive API (no key)",
            },
            "stations": {str(k): v for k, v in STATIONS.items()},
            "window": {"start": START, "end": END},
            "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "snapshot_sha256": digest,
            "row_counts": {"station": len(station_rows), "weather": len(weather_rows)},
        },
        "stations": station_rows,
        "weather": weather_rows,
    }
    (OUT / "training_snapshot.json").write_text(json.dumps(payload))
    print(f"snapshot sha256: {digest}", file=sys.stderr)
    print(f"wrote {OUT / 'training_snapshot.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
