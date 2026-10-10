"""Build the DEMO_MODE snapshot from a real archive fetch.

Recorded data lives under fixtures/demo/ and is ONLY served when
DEMO_MODE=1, with a permanent visible banner in the UI (rule 1).
Provenance is written next to the data.

Usage: uv run python scripts/build_demo_snapshot.py
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures" / "demo"
ARCHIVE = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz"
# OpenAQ location ids in Delhi-NCR discovered by probing the public archive
# (2026-10-15): see docs/DATA_SOURCES.md "Delhi station discovery" section.
LOCATIONS = [8118]
DAYS = 7  # a few real days of hourly readings, starting 2024-01-09


def fetch_day(location_id: int, date: str) -> str:
    url = (
        f"{ARCHIVE}/locationid={location_id}/year=2024/month=01/"
        f"location-{location_id}-{date}.csv.gz"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - fixed https URL
        return gzip.decompress(resp.read()).decode()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in range(9, 9 + DAYS):
        date = datetime.strptime(f"2024-01-{d:02d}", "%Y-%m-%d").strftime("%Y%m%d")
        for loc in LOCATIONS:
            try:
                text = fetch_day(loc, date)
            except Exception as exc:  # noqa: BLE001
                print(f"skip {loc} {date}: {exc}")
                continue
            reader = csv.DictReader(io.StringIO(text))
            for r in reader:
                if r.get("parameter") != "pm25":
                    continue
                rows.append(
                    {
                        "location_id": r["location_id"],
                        "sensors_id": r["sensors_id"],
                        "location": r["location"],
                        "datetime": r["datetime"],
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                        "parameter": r["parameter"],
                        "units": r["units"],
                        "value": float(r["value"]),
                    }
                )
    payload = {
        "provenance": {
            "source": "OpenAQ public archive bucket (no credentials required)",
            "url": ARCHIVE,
            "license": "CC BY 4.0 - attribution: OpenAQ",
            "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "locations": LOCATIONS,
            "window": f"2024-01-09 .. {8 + DAYS}",
            "note": "RECORDED data for DEMO_MODE only; never served as live.",
        },
        "readings": rows,
    }
    (OUT / "openaq_recorded.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote {len(rows)} readings to {OUT}/openaq_recorded.json")


if __name__ == "__main__":
    main()
