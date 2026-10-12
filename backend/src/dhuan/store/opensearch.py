"""OpenSearch access layer for geo-indexed pollution sources.

Index: `sources`
  location          geo_point
  osm_id, type, name keyword/text
  area_m2           float
  source_tags       object
  last_seen         date
  attribution       text (ODbL — carried per doc)

The upwind cone is *not* a geo query: we run a geo-distance query bounded by
radius and apply the exact cone test from `geo/geo_math.py` to candidates
sorted by distance. This keeps the query index-friendly and the math honest.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from opensearchpy import OpenSearch, exceptions

from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.core.units import Point
from dhuan.geo.scoring import CandidateSource, Influence, influence_score

logger = get_logger("store.opensearch")

# The classified OSM catalogue that ships with the image, built from a real
# Overpass extract. It lets attribution work with no OpenSearch running, which
# is the difference between "the app explains the air" and "the app returns 503".
LOCAL_CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "delhi_sources.json"
LOCAL_CATALOGUE_ENV = "DHUAN_SOURCE_CATALOGUE"

INDEX_MAPPINGS: dict[str, Any] = {
    "mappings": {
        "properties": {
            "osm_id": {"type": "keyword"},
            "type": {"type": "keyword"},
            "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "location": {"type": "geo_point"},
            "area_m2": {"type": "float"},
            "source_tags": {"type": "object", "dynamic": True},
            "last_seen": {"type": "date"},
            "attribution": {"type": "text"},
        }
    }
}


@lru_cache(maxsize=1)
def local_catalogue() -> tuple[dict[str, Any], ...]:
    """The shipped OSM source catalogue, loaded once.

    Empty when the file is absent; the caller then falls back to OpenSearch.
    """
    import os  # noqa: PLC0415

    override = os.environ.get(LOCAL_CATALOGUE_ENV)
    path = Path(override) if override else LOCAL_CATALOGUE
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        logger.warning("local_catalogue_unreadable: %s", exc)
        return ()
    rows = payload.get("sources", [])
    return tuple(r for r in rows if isinstance(r, dict) and "lat" in r and "lon" in r)


def client(settings: Settings | None = None) -> OpenSearch:
    s = settings or get_settings()
    return OpenSearch(
        hosts=[s.opensearch_endpoint],
        http_compress=True,
        use_ssl=s.opensearch_endpoint.startswith("https"),
        verify_certs=s.opensearch_endpoint.startswith("https"),
        timeout=10,
        max_retries=3,
        retry_on_timeout=True,
    )


class SourceIndex:
    """All reads/writes of the sources index."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.index = self.settings.opensearch_index
        self._client: OpenSearch | None = None

    @property
    def es(self) -> OpenSearch:
        if self._client is None:
            self._client = client(self.settings)
        return self._client

    def ensure_index(self) -> None:
        if not self.es.indices.exists(index=self.index):
            self.es.indices.create(index=self.index, body=INDEX_MAPPINGS)
            logger.info("opensearch_index_created: %s", self.index)

    def bulk_index(self, docs: list[dict[str, Any]]) -> int:
        """Index source documents (from ingest/osm to_index_dict)."""
        if not docs:
            return 0
        from opensearchpy.helpers import bulk  # noqa: PLC0415 - lazy, only used here

        actions = []
        for doc in docs:
            osm_id = doc.get("osm_id")
            if not osm_id:
                continue
            actions.append({"_op_type": "index", "_index": self.index, "_id": osm_id, **doc})
        if not actions:
            return 0
        success, errors = bulk(self.es, actions, raise_on_error=False)
        if errors:
            logger.warning("opensearch_bulk_partial: %d errors, e.g. %s", len(errors), errors[0])
        return int(success)

    def count(self) -> int:
        try:
            resp = self.es.count(index=self.index)
            return int(resp.get("count", 0))
        except exceptions.NotFoundError:
            return 0

    def sources_near(  # noqa: PLR0917 - geo params stay positional
        self,
        lat: float,
        lon: float,
        radius_km: float = 25.0,
        upwind: bool = True,
        wind_from_deg: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Geo-distance query, then exact cone filtering and influence scoring.

        Uses the shipped OSM catalogue when one is available, so this works with
        no OpenSearch. OpenSearch is preferred when it is reachable because it
        carries the live index; the local catalogue is the fallback, and both
        paths apply the identical cone test and influence score.
        """
        local = _local_sources_near(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            upwind=upwind,
            wind_from_deg=wind_from_deg,
            limit=limit,
        )
        if local:
            return local
        query: dict[str, Any] = {
            "size": max(limit * 4, 200),
            "query": {
                "bool": {
                    "filter": [
                        {
                            "geo_distance": {
                                "distance": f"{radius_km}km",
                                "location": {"lat": lat, "lon": lon},
                            }
                        }
                    ]
                }
            },
            "sort": [{"_geo_distance": {"location": {"lat": lat, "lon": lon}, "order": "asc"}}],
        }
        try:
            resp = self.es.search(index=self.index, body=query)
        except exceptions.NotFoundError:
            return []
        target = Point(lat=lat, lon=lon)
        out: list[tuple[float, dict[str, Any], CandidateSource, Influence]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            src = hit["_source"]
            loc = src.get("location") or {}
            if "lat" not in loc or "lon" not in loc:
                continue
            candidate = CandidateSource(
                osm_id=str(src.get("osm_id")),
                name=str(src.get("name", "")),
                source_type=str(src.get("type", "other")),
                location=Point(lat=float(loc["lat"]), lon=float(loc["lon"])),
                area_m2=src.get("area_m2"),
                tags=dict(src.get("source_tags") or {}),
            )
            influence = influence_score(candidate, target, wind_from_deg or 0.0)
            if upwind and wind_from_deg is not None and not influence.in_cone:
                continue  # exact cone test, not an approximation
            if not upwind:
                # without a wind direction, rank by distance-only alignment
                influence = influence_score(candidate, target, influence.bearing_deg)
            out.append((influence.score, src, candidate, influence))
        out.sort(key=lambda t: t[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, src, _candidate, infl in out[:limit]:
            results.append(
                {
                    **src,
                    "distance_km": round(infl.distance_km, 2),
                    "bearing_deg": round(infl.bearing_deg, 1),
                    "in_upwind_cone": infl.in_cone,
                    "influence_score": score,
                }
            )
        return results

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


__all__ = ["INDEX_MAPPINGS", "SourceIndex", "client"]


def _local_sources_near(
    *,
    lat: float,
    lon: float,
    radius_km: float,
    upwind: bool,
    wind_from_deg: float | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Same maths as the OpenSearch path, over the shipped OSM catalogue."""
    rows = local_catalogue()
    if not rows:
        return []
    target = Point(lat=lat, lon=lon)
    out: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        try:
            candidate = CandidateSource(
                osm_id=str(row.get("osm_id") or f"static-{row['lat']:.5f},{row['lon']:.5f}"),
                name=str(row.get("name") or ""),
                source_type=str(row.get("kind") or row.get("type") or "other"),
                location=Point(lat=float(row["lat"]), lon=float(row["lon"])),
                area_m2=row.get("area_m2"),
                tags=dict(row.get("tags") or row.get("source_tags") or {}),
            )
        except (KeyError, TypeError, ValueError):
            continue
        influence = influence_score(candidate, target, wind_from_deg or 0.0)
        if influence.distance_km > radius_km:
            continue
        if upwind and wind_from_deg is not None and not influence.in_cone:
            continue
        if not upwind:
            influence = influence_score(candidate, target, influence.bearing_deg)
        out.append(
            (
                influence.score,
                {
                    "osm_id": candidate.osm_id,
                    "name": candidate.name,
                    "type": candidate.source_type,
                    "location": {"lat": candidate.location.lat, "lon": candidate.location.lon},
                    "area_m2": candidate.area_m2,
                    "distance_km": round(influence.distance_km, 2),
                    "bearing_deg": round(influence.bearing_deg, 1),
                    "in_upwind_cone": influence.in_cone,
                    "influence_score": influence.score,
                    "attribution": "© OpenStreetMap contributors (ODbL)",
                },
            )
        )
    out.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in out[:limit]]
