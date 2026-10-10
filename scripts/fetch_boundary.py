#!/usr/bin/env python3
"""Fetch real NCT-of-Delhi + NCR district boundaries from OpenStreetMap and
build a simplified coverage polygon for the app.

Provenance is recorded inside the output file (source, OSM ids, fetch date).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone

MIRRORS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

NCR_NAMES = [
    "Delhi", "Gurugram", "Gurgaon", "Faridabad", "Nuh", "Rohtak", "Sonipat", "Sonepat",
    "Meerut", "Ghaziabad", "Gautam Buddha Nagar", "Gautam Budh Nagar", "Bulandshahr",
    "Baghpat", "Hapur", "Muzaffarnagar", "Shamli", "Alwar", "Bharatpur",
]

QUERY = """
[out:json][timeout:60];
(
  relation["boundary"="administrative"]["admin_level"~"^(4|5)$"](26.9,76.3,29.3,78.4);
);
out geom;
"""


def fetch() -> dict:
    body = QUERY.encode()
    last = None
    for url in MIRRORS:
        try:
            req = urllib.request.Request(
                url, data=body, headers={"User-Agent": "DhuanDetective/1.0 boundary fetch"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"mirror failed {url}: {exc}", file=sys.stderr)
    raise SystemExit(f"all mirrors failed: {last}")


def ring_from_members(rel: dict) -> list[list[float]] | None:
    """Stitch outer way members into one polygon ring."""
    segments: list[list[tuple[float, float]]] = []
    for m in rel.get("members", []):
        if m.get("type") == "way" and m.get("role") == "outer" and m.get("geometry"):
            pts = [(g["lon"], g["lat"]) for g in m["geometry"]]
            if len(pts) >= 2:
                segments.append(pts)
    if not segments:
        return None
    ring = list(segments[0])
    used = {0}
    changed = True
    while changed:
        changed = False
        end = ring[-1]
        for i, seg in enumerate(segments):
            if i in used:
                continue
            if seg[0] == end:
                ring.extend(seg[1:])
                used.add(i)
                changed = True
                break
            if seg[-1] == end:
                ring.extend(list(reversed(seg[:-1])))
                used.add(i)
                changed = True
                break
    if len(ring) < 4 or ring[0] != ring[-1]:
        return None
    return ring


def simplify(ring: list[list[float]], tol_deg: float = 0.005) -> list[list[float]]:
    """Radial-distance simplification."""
    out = [ring[0]]
    for p in ring[1:]:
        if abs(p[0] - out[-1][0]) > tol_deg or abs(p[1] - out[-1][1]) > tol_deg:
            out.append(p)
    if out[-1] != ring[-1]:
        out.append(ring[-1])
    return out


def main() -> None:
    data = fetch()
    polys = []
    ids = []
    for rel in data.get("elements", []):
        name = rel.get("tags", {}).get("name", "")
        if not any(n.lower() in name.lower() for n in NCR_NAMES):
            continue
        ring = ring_from_members(rel)
        if ring is None:
            print(f"skip {name}: could not build ring", file=sys.stderr)
            continue
        polys.append([simplify(ring)])
        ids.append({"name": name, "osm_id": f"relation/{rel['id']}", "admin_level": rel.get("tags", {}).get("admin_level")})
        print(f"kept {name} ({rel['id']}): {len(ring)} pts -> {len(polys[-1][0])} pts")
    fc = {
        "type": "FeatureCollection",
        "name": "delhi-ncr-coverage",
        "provenance": {
            "source": "OpenStreetMap via Overpass API",
            "license": "ODbL 1.0 (© OpenStreetMap contributors)",
            "attribution": "© OpenStreetMap contributors",
            "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "query": "relation[boundary=administrative][admin_level~^(4|5)$](26.9,76.3,29.3,78.4); out geom;",
            "mirror_used": MIRRORS[0],
            "simplification_deg": 0.005,
            "relations": ids,
        },
        "features": [
            {"type": "Feature", "properties": {"name": p["name"], "osm_id": p["osm_id"]},
             "geometry": {"type": "Polygon", "coordinates": poly}}
            for p, poly in zip(ids, polys)
        ],
    }
    out = "/Users/viclkykumar/pollution/backend/src/dhuan/geo/ncr_boundary.geojson"
    with open(out, "w") as f:
        json.dump(fc, f, separators=(",", ":"))
    print(f"wrote {out} with {len(polys)} polygons")


if __name__ == "__main__":
    main()
