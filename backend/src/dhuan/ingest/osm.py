"""OpenStreetMap pollution-source ingestion via Overpass API.

Verified 2026-10-15: POST `https://<mirror>/api/interpreter` with
`[out:json]` QL. The primary endpoint rate-limits aggressively, so mirrors
are tried in order (`overpass.private.coffee`, `overpass.kumi.systems`,
`overpass-api.de`). OSM data is ODbL 1.0: attribution is mandatory and is
carried on every source document.

Extracted candidate source types (documented in docs/DATA_SOURCES.md):
  * landfill       landuse=landfill
  * industrial     landuse=industrial
  * construction   landuse=construction
  * major_junction node[highway=traffic_signals] (capped, this is a proxy for
                  dense traffic junctions, not a smoke source itself)
Areas come from closed ways (rings); points from nodes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dhuan.core.config import Settings, get_settings
from dhuan.core.http import HttpPolicy, make_client, make_request
from dhuan.core.logging import get_logger
from dhuan.core.units import Point
from dhuan.geo.scoring import CandidateSource

logger = get_logger("ingest.osm")

OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL 1.0)"

# QL fragments per source type. Junctions are capped server-side-ish to keep
# the index useful; see osm_test_fixtures for scale.
QUERY_TYPES: dict[str, str] = {
    "landfill": 'way["landuse"="landfill"]',
    "industrial": 'way["landuse"="industrial"]',
    "construction": 'way["landuse"="construction"]',
    "major_junction": 'node["highway"="traffic_signals"]',
}


@dataclass(slots=True)
class OsmSourceDoc:
    """A source document ready for OpenSearch indexing."""

    osm_id: str
    type: str
    name: str
    location: Point
    area_m2: float | None
    source_tags: dict[str, str]
    last_seen: str

    def to_index_dict(self) -> dict[str, object]:
        return {
            "osm_id": self.osm_id,
            "type": self.type,
            "name": self.name,
            "location": {"lat": self.location.lat, "lon": self.location.lon},
            "area_m2": self.area_m2,
            "source_tags": self.source_tags,
            "last_seen": self.last_seen,
            "attribution": OSM_ATTRIBUTION,
        }

    def as_candidate(self) -> CandidateSource:
        return CandidateSource(
            osm_id=self.osm_id,
            name=self.name,
            source_type=self.type,
            location=self.location,
            area_m2=self.area_m2,
            tags=self.source_tags,
        )


class OverpassClient:
    """POSTs QL to Overpass mirrors in order, first success wins."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        # Overpass mirrors reject generic UA strings; a contact UA is required
        # by their usage policy (verified 2026-10-15).
        self._client = make_client(
            HttpPolicy.from_settings(self.settings),
            headers={"User-Agent": "DhuanDetective/1.0 (contact: team@dhuan-detective.example)"},
        )
        self.endpoints = list(self.settings.overpass_endpoints)

    async def query(self, ql: str) -> dict[str, Any]:
        policy = HttpPolicy.from_settings(self.settings)
        last_exc: Exception | None = None
        for endpoint in self.endpoints:
            try:
                resp = await make_request(
                    self._client,
                    policy,
                    "overpass",
                    "POST",
                    endpoint,
                    data={"data": ql},
                    headers={"Accept": "application/json"},
                )
            except Exception as exc:  # try the next mirror
                last_exc = exc
                logger.warning("overpass_mirror_failed %s: %s", endpoint, exc)
                continue
            data: dict[str, Any] = resp.json()
            return data
        raise last_exc if last_exc else RuntimeError("no overpass endpoints")

    async def aclose(self) -> None:
        """Close the current client and leave this instance reusable.

        These clients are cached process-wide in api/deps.py, and a Lambda
        container handles many invocations. Closing the client without
        replacing it left the cache holding a closed httpx client, so the next
        invocation raised "Cannot send a request, as the client has been
        closed" and the task silently degraded to a branch failure. Each
        invocation also runs its own event loop, so a client bound to a
        finished loop cannot be reused anyway - rebuild it here.
        """
        await self._client.aclose()
        self._client = make_client(HttpPolicy.from_settings(self.settings))


def build_query(
    west: float, south: float, east: float, north: float, types: list[str] | None = None
) -> str:
    types = types or list(QUERY_TYPES)
    bbox = f"({south},{west},{north},{east})"
    parts = [f"  {QUERY_TYPES[t]}{bbox};" for t in types if t in QUERY_TYPES]
    return "[out:json][timeout:60];\n(\n" + "\n".join(parts) + "\n);\nout geom;\n"


def _ring_area_m2(geom: list[dict[str, float]]) -> float | None:
    """Shoelace area on an equirectangular projection (fine at city scale)."""
    if len(geom) < 4:
        return None
    lat0 = geom[0]["lat"]
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    pts = [(g["lon"] * m_per_deg_lon, g["lat"] * m_per_deg_lat) for g in geom]
    area = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def parse_overpass(payload: dict[str, Any], fetched_at: str) -> list[OsmSourceDoc]:
    """Convert an Overpass `out geom` payload into source documents."""
    docs: list[OsmSourceDoc] = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        el_type = el.get("type")
        el_id = el.get("id")
        if el_type == "way":
            geom = el.get("geometry") or []
            if not geom:
                continue
            lat = sum(g["lat"] for g in geom) / len(geom)
            lon = sum(g["lon"] for g in geom) / len(geom)
            area = _ring_area_m2(geom) if geom[0] == geom[-1] else None
        elif el_type == "node":
            lat = float(el["lat"])
            lon = float(el["lon"])
            area = None
        else:
            continue  # relations are not needed for our source types
        stype = _classify(tags)
        name = tags.get("name") or tags.get("operator") or _default_name(stype)
        docs.append(
            OsmSourceDoc(
                osm_id=f"{el_type}/{el_id}",
                type=stype,
                name=name,
                location=Point(lat=lat, lon=lon),
                area_m2=area,
                source_tags={
                    k: v
                    for k, v in tags.items()
                    if k in {"name", "operator", "landuse", "highway", "surface", "access"}
                },
                last_seen=fetched_at,
            )
        )
    return docs


def _classify(tags: dict[str, str]) -> str:
    if tags.get("landuse") == "landfill":
        return "landfill"
    if tags.get("landuse") == "industrial":
        return "industrial"
    if tags.get("landuse") == "construction":
        return "construction"
    if tags.get("highway") == "traffic_signals":
        return "major_junction"
    return "other"


def _default_name(stype: str) -> str:
    labels = {
        "landfill": "Unnamed landfill (area)",
        "industrial": "Unnamed industrial area",
        "construction": "Unnamed construction site",
        "major_junction": "Signalised junction",
        "other": "Unnamed candidate source",
    }
    return labels[stype]


async def fetch_sources_for_bbox(
    west: float, south: float, east: float, north: float, settings: Settings | None = None
) -> list[OsmSourceDoc]:
    client = OverpassClient(settings)
    try:
        ql = build_query(west, south, east, north)
        payload = await client.query(ql)

        docs = parse_overpass(payload, datetime.now(UTC).isoformat(timespec="seconds"))
        logger.info("osm_sources_parsed: %d", len(docs))
        return docs
    finally:
        await client.aclose()


__all__ = [
    "OSM_ATTRIBUTION",
    "OsmSourceDoc",
    "OverpassClient",
    "build_query",
    "fetch_sources_for_bbox",
    "parse_overpass",
]
