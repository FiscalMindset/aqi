"""Fetch static land-use context around the Indian training stations.

Same Overpass query family as the Delhi seed (verified; mirrors in order,
contact UA required). Results are stored per city for feature building.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
UA = {"User-Agent": "DhuanDetective/1.0 (contact: team@dhuan-detective.example)"}

STATIONS = {
    8118: (28.63576, 77.22445),
    931708: (13.08784, 80.278475),
    8557: (17.38405, 78.45636),
    8039: (19.07283, 72.88261),
}
OUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "static_sources"

QUERY_TMPL = """
[out:json][timeout:90];
(
  way["landuse"="landfill"]({s},{w},{n},{e});
  way["landuse"="industrial"]({s},{w},{n},{e});
  way["landuse"="construction"]({s},{w},{n},{e});
  node["highway"="traffic_signals"]({s},{w},{n},{e});
);
out geom;
"""


def post_query(ql: str) -> dict[str, object]:
    last = None
    for url in MIRRORS:
        try:
            req = urllib.request.Request(url, data=ql.encode(), headers=UA)
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.load(resp)
            if "elements" in payload:
                return payload
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last = exc
            print(f"  mirror failed {url}: {exc}", file=sys.stderr)
    raise SystemExit(f"all mirrors failed: {last}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for loc, (lat, lon) in STATIONS.items():
        pad = 0.15 if loc == 8039 else 0.3  # Mumbai bbox is too heavy at 0.3 deg
        s, w, n, e = lat - pad, lon - pad, lat + pad, lon + pad
        ql = QUERY_TMPL.format(s=s, w=w, n=n, e=e)
        payload = post_query(ql)
        for el in payload.get("elements", []):
            el["_center_lat"], el["_center_lon"] = lat, lon
        wrapper = {
            "provenance": {
                "source": "OpenStreetMap via Overpass API (ODbL)",
                "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "bbox": [s, w, n, e],
                "station_location_id": loc,
            },
            "elements": payload.get("elements", []),
        }
        path = OUT / f"station_{loc}.json"
        path.write_text(json.dumps(wrapper))
        print(f"{path.name}: {len(wrapper['elements'])} elements")


if __name__ == "__main__":
    main()
