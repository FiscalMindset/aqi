#!/usr/bin/env python3
"""Build the compact station index that the API serves from.

The training snapshot holds 591k rows, which is far too much to load on a cold
Lambda start. What the API actually needs is small: for each station, its latest
PM2.5 reading plus the last few hours of history (enough for a trend and for the
persistence anchor).

This script distils the snapshot into that. It reads only the training snapshot,
which was itself built from the OpenAQ public archive, so the served data is real
historical data with a real provenance block.

Run:  python scripts/build_station_index.py
"""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
SNAPSHOT = BACKEND / "data" / "training_snapshot.json.gz"
INDEX = BACKEND / "data" / "station_index.json"

# How many hours of history per station to keep for trend and anchoring.
HISTORY_HOURS = 48


def load_snapshot() -> dict[str, object]:
    if SNAPSHOT.exists():
        with gzip.open(SNAPSHOT, "rt") as handle:
            return json.load(handle)
    raw = BACKEND / "data" / "training_snapshot.json"  # uncompressed variant
    return json.loads(raw.read_text())


def main() -> int:
    payload = load_snapshot()
    provenance = payload.get("provenance", {})
    rows = payload.get("stations", [])
    if not isinstance(rows, list) or not rows:
        print("no station rows in snapshot")
        return 1

    by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    meta: dict[str, dict[str, object]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        location_id = str(row.get("location_id", ""))
        if not location_id:
            continue
        try:
            observed = datetime.fromisoformat(str(row["datetime"])).astimezone(UTC)
        except (KeyError, ValueError):
            continue
        by_station[location_id].append(
            {
                "t": observed.isoformat(),
                "v": float(row["value"]),
            }
        )
        meta.setdefault(
            location_id,
            {
                "name": row.get("location"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "sensor_id": row.get("sensor_id"),
            },
        )

    stations: list[dict[str, object]] = []
    for location_id, series in by_station.items():
        series.sort(key=lambda r: str(r["t"]))
        # keep only the most recent HISTORY_HOURS of the series
        trimmed = series[-HISTORY_HOURS:]
        info = meta[location_id]
        stations.append(
            {
                "location_id": location_id,
                "name": info["name"],
                "lat": float(info["lat"]),  # type: ignore[arg-type]
                "lon": float(info["lon"]),  # type: ignore[arg-type]
                "sensor_id": info["sensor_id"],
                "latest": trimmed[-1],
                "history": trimmed,
            }
        )

    stations.sort(key=lambda s: str(s["name"] or ""))
    newest = max(
        (str(s["latest"]["t"]) for s in stations if isinstance(s.get("latest"), dict)),
        default=None,
    )

    index = {
        "schema": 1,
        "provenance": {
            **provenance,
            # a canonical single field so readers do not have to know the
            # nested shape the snapshot builder happened to use
            "source": "openaq-public-archive",
            "built_by": "scripts/build_station_index.py",
            "built_utc": datetime.now(UTC).isoformat(),
            "note": (
                "Derived from the OpenAQ public archive training snapshot. Real "
                "historical observations, not synthetic."
            ),
            "stations": len(stations),
            "history_hours": HISTORY_HOURS,
            "newest_observation": newest,
        },
        "stations": stations,
    }
    INDEX.write_text(json.dumps(index, separators=(",", ":")))
    size_kb = INDEX.stat().st_size / 1024
    print(f"wrote {INDEX} ({size_kb:.1f} KB, {len(stations)} stations, newest {newest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())