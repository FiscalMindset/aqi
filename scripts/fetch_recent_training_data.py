#!/usr/bin/env python3
"""Extract a RECENT training snapshot from the OpenAQ public archive.

The original snapshot covered 2023-06..2023-12 from four stations. This builds a
fresher one from every Delhi-NCR monitoring station the archive publishes
(DPCC, CPCB, IMD, UPPCB and HSPCB networks), covering the most recent months.

No credentials: the archive is a public S3 bucket, one gzipped CSV per station
per day. Weather comes from the Open-Meteo archive API, which also needs no key.

Writes backend/data/training_snapshot.json and prints the provenance block.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ARCHIVE = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz"
BUCKET = "https://openaq-data-archive.s3.amazonaws.com/"
WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"
OUT = Path(__file__).resolve().parents[1] / "backend" / "data"

# Delhi-NCR bounding box used to select stations.
LAT_MIN, LAT_MAX = 28.30, 28.95
LON_MIN, LON_MAX = 76.75, 77.65

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
MIN_ROWS_PER_STATION = 200
UA = {"User-Agent": "DhuanDetective/1.0 (open-source air quality project)"}


def _get(url: str, timeout: int = 60, byte_range: str | None = None) -> bytes:
    headers = dict(UA)
    if byte_range:
        headers["Range"] = byte_range
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https
        return resp.read()


def discover_stations(target_day: str) -> list[dict[str, Any]]:
    """Every location id in the bucket whose data falls inside the NCR box."""
    ids: list[int] = []
    token = ""
    while True:
        url = (
            f"{BUCKET}?list-type=2&prefix=records/csv.gz/locationid=&delimiter=/&max-keys=1000"
        )
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        xml = _get(url).decode()
        ids += [int(x) for x in __import__("re").findall(r"locationid=(\d+)/", xml)]
        m = __import__("re").search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            break
        token = m.group(1)
    ids = sorted(set(ids))
    sys.stderr.write(f"discovered {len(ids)} archive locations\n")

    def probe(loc: int) -> dict[str, Any] | None:
        url = (
            f"{ARCHIVE}/locationid={loc}/year={target_day[:4]}/month={target_day[4:6]}"
            f"/location-{loc}-{target_day}.csv.gz"
        )
        try:
            raw = _get(url, timeout=20, byte_range="bytes=0-6000")
            text = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, 40000)
            text = text.decode("utf-8", "ignore")
        except Exception:
            return None
        lines = text.splitlines()
        if len(lines) < 2:
            return None
        for row in csv.DictReader(io.StringIO("\n".join(lines))):
            if row.get("parameter") != "pm25":
                continue
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (KeyError, ValueError):
                return None
            if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                return None
            return {"id": loc, "lat": lat, "lon": lon, "name": row.get("location", str(loc))}
        return None

    with ThreadPoolExecutor(max_workers=96) as pool:
        found = [r for r in pool.map(probe, ids) if r]
    found.sort(key=lambda s: s["id"])
    sys.stderr.write(f"{len(found)} stations inside Delhi-NCR\n")
    return found


def fetch_station(loc: int, days: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in days:
        url = (
            f"{ARCHIVE}/locationid={loc}/year={day[:4]}/month={day[4:6]}"
            f"/location-{loc}-{day}.csv.gz"
        )
        try:
            text = gzip.decompress(_get(url, timeout=45)).decode()
        except Exception:  # noqa: BLE001 - a missing day is normal
            continue
        for r in csv.DictReader(io.StringIO(text)):
            if r.get("parameter") != "pm25":
                continue
            try:
                rows.append(
                    {
                        "location_id": int(r["location_id"]),
                        "sensor_id": int(r["sensors_id"]),
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                        # keys must match what dhuan.model.features expects
                        "datetime": r["datetime"],
                        "value": float(r["value"]),
                        "location": r.get("location", str(loc)),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def fetch_weather(lat: float, lon: float, start: str, end: str) -> list[dict[str, Any]]:
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(
            [
                "temperature_2m", "relative_humidity_2m", "precipitation",
                "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
                "surface_pressure",
            ]
        ),
    }
    try:
        payload = json.loads(_get(f"{WEATHER_API}?{urllib.parse.urlencode(params)}", timeout=90))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"  weather {lat},{lon} failed: {exc}\n")
        return []
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    out: list[dict[str, Any]] = []
    for i, ts in enumerate(times):
        out.append(
            {
                "lat": float(params["latitude"]),
                "lon": float(params["longitude"]),
                "time": ts,
                "temp_c": hourly["temperature_2m"][i],
                "rh": hourly["relative_humidity_2m"][i],
                "precip": hourly["precipitation"][i],
                "wind_speed": hourly["wind_speed_10m"][i],
                "wind_dir": hourly["wind_direction_10m"][i],
                "wind_gust": hourly["wind_gusts_10m"][i],
                "pressure": hourly.get("surface_pressure", [None] * len(times))[i],
            }
        )
    return out


def main() -> int:
    today = date.today()
    start_date = today - timedelta(days=DAYS)
    days = [(start_date + timedelta(days=i)).strftime("%Y%m%d") for i in range(DAYS + 1)]
    probe_day = (today - timedelta(days=45)).strftime("%Y%m%d")

    stations = discover_stations(probe_day)
    if not stations:
        print("no NCR stations discovered", file=sys.stderr)
        return 2

    def work(st: dict[str, Any]) -> dict[str, Any]:
        rows = fetch_station(st["id"], days)
        if len(rows) < MIN_ROWS_PER_STATION:
            return {**st, "rows": []}
        return {**st, "rows": rows}

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(work, stations))
    kept = [r for r in results if r["rows"]]
    sys.stderr.write(f"{len(kept)} stations had >= {MIN_ROWS_PER_STATION} pm25 rows\n")

    station_rows: list[dict[str, Any]] = []
    for r in kept:
        station_rows.extend(r["rows"])
        sys.stderr.write(f"  {r['name'][:46]:46} {len(r['rows']):5} rows\n")

    weather_rows: list[dict[str, Any]] = []
    for r in kept:
        weather_rows.extend(
            fetch_weather(r["lat"], r["lon"], start_date.isoformat(), today.isoformat())
        )
        time.sleep(0.2)

    payload: dict[str, Any] = {
        "provenance": {
            "sources": {
                "stations": "OpenAQ public archive bucket (no credentials)",
                "weather": "Open-Meteo archive API (no key)",
            },
            "stations": {str(r["id"]): [r["lat"], r["lon"]] for r in kept},
            "station_names": {str(r["id"]): r["name"] for r in kept},
            "window": {"start": start_date.isoformat(), "end": today.isoformat()},
            "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "row_counts": {"station": len(station_rows), "weather": len(weather_rows)},
        },
        "stations": station_rows,
        "weather": weather_rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "training_snapshot.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    sys.stderr.write(f"\nwrote {path} ({path.stat().st_size / 1e6:.1f} MB)\n")
    print(json.dumps(payload["provenance"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())