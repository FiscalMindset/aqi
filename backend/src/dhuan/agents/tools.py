"""Typed tools for the attribution agent.

Each tool:
  * has a JSON schema (name, description, parameters) — used by both the
    Bedrock Converse path and the scripted path,
  * returns plain JSON-safe data,
  * records an EvidenceItem into the run's trace so every claim can be tied
    back to the exact call that produced it.

Guardrail: tool output is DATA. Nothing a tool returns is ever executed or
interpreted as instructions (see guardrails.py).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dhuan.api.deps import get_fires, get_source_index
from dhuan.api.services import nearest_reading, stations_near, weather_now
from dhuan.core.config import get_settings
from dhuan.core.units import Point, haversine_km
from dhuan.ingest.openaq import NotConfiguredError

EVIDENCE_PREFIX = "ev"


def new_evidence_id() -> str:
    return f"{EVIDENCE_PREFIX}_{uuid4().hex[:12]}"


@dataclass(slots=True)
class Evidence:
    evidence_id: str
    tool: str
    args: dict[str, Any]
    result: Any
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ok: bool = True
    note: str | None = None

    def to_item(self, summary: str) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "tool": self.tool,
            "args": self.args,
            "summary": summary,
            "fetched_at": self.fetched_at,
            "ok": self.ok,
            "note": self.note,
            # the raw tool payload travels with the evidence so synthesis and
            # the UI can use the structured result, not just the summary
            "result": self.result,
        }


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


def _point_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "minimum": -90, "maximum": 90},
            "lon": {"type": "number", "minimum": -180, "maximum": 180},
            "radius_km": {"type": "number", "minimum": 0.5, "maximum": 50, "default": 10},
        },
        "required": ["lat", "lon"],
    }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.trace: list[Evidence] = []

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def specs(self) -> list[dict[str, Any]]:
        return [self._tools[n].schema() for n in sorted(self._tools)]

    def reset_trace(self) -> None:
        self.trace.clear()

    async def run(self, name: str, args: dict[str, Any]) -> Evidence:
        """Execute a tool, record evidence, and return JSON-safe data holder."""
        spec = self._tools.get(name)
        ev_id = new_evidence_id()
        if spec is None:
            evidence = Evidence(ev_id, name, args, None, ok=False, note="unknown tool")
            self.trace.append(evidence)
            return evidence
        try:
            result = await spec.handler(**args)
            evidence = Evidence(ev_id, name, args, result, ok=True)
        except Exception as exc:
            evidence = Evidence(
                ev_id, name, args, None, ok=False, note=f"tool failed: {exc}"
            )
        self.trace.append(evidence)
        return evidence

    def evidence_items(self) -> list[dict[str, Any]]:
        return [e.to_item(_summarize(e)) for e in self.trace]

    def ids(self) -> set[str]:
        return {e.evidence_id for e in self.trace}


def _summarize(evidence: Evidence) -> str:
    if not evidence.ok:
        return evidence.note or "tool failed"
    payload = evidence.result
    if isinstance(payload, dict):
        for key in ("summary", "message"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(payload, default=str)[:200]
    return str(payload)[:200]


def default_registry(
    *, fire_client: Any = None, source_index: Any = None
) -> ToolRegistry:
    """Registry with the five production tools wired to real services."""

    async def get_air_and_wind(lat: float, lon: float) -> dict[str, Any]:
        wx = await weather_now(lat, lon)
        if wx.data is None:
            return {"ok": False, "summary": "weather unavailable"}
        w = wx.data
        return {
            "ok": True,
            "summary": (
                f"wind {w.wind_speed_ms:.1f} m/s from {w.wind_direction_deg:.0f} deg, "
                f"temp {w.temperature_c:.1f}C, RH {w.relative_humidity_pct:.0f}%"
            ),
            "wind_speed_ms": round(w.wind_speed_ms, 2),
            "wind_from_deg": round(w.wind_direction_deg, 1),
            "temperature_c": round(w.temperature_c, 1),
            "relative_humidity_pct": round(w.relative_humidity_pct, 0),
            "precipitation_mm": round(w.precipitation_mm, 1),
            "data_age_seconds": round(wx.age_seconds, 1),
            "stale": wx.stale,
        }

    async def find_upwind_sources(lat: float, lon: float, radius_km: float = 10) -> dict[str, Any]:
        index = source_index or get_source_index()

        wx = await weather_now(lat, lon)
        wind = wx.data.wind_direction_deg if wx.data else None
        hits = index.sources_near(
            lat=lat, lon=lon, radius_km=radius_km, upwind=True, wind_from_deg=wind, limit=20
        )
        slim = [
            {
                "type": h.get("type"),
                "name": h.get("name"),
                "distance_km": h.get("distance_km"),
                "bearing_deg": h.get("bearing_deg"),
                "influence_score": h.get("influence_score"),
            }
            for h in hits
        ]
        return {
            "ok": True,
            "summary": f"{len(slim)} candidate sources within {radius_km} km upwind",
            "wind_from_deg": wind,
            "sources": slim,
            "attribution": "© OpenStreetMap contributors (ODbL)",
        }

    async def get_recent_fires(
        lat: float, lon: float, radius_km: float = 50
    ) -> dict[str, Any]:
        client = fire_client or get_fires()
        try:
            fires = await client.recent_in_ncr(day_range=3)
        except NotConfiguredError:
            return {
                "ok": False,
                "summary": "fire feed unavailable (no MAP_KEY configured)",
                "fires_count": None,
            }
        center = Point(lat, lon)
        nearby = [
            f
            for f in fires
            if haversine_km(center, Point(lat=f.latitude, lon=f.longitude)) <= radius_km
        ]
        return {
            "ok": True,
            "summary": f"{len(nearby)} fire detections within {radius_km} km in the last 3 days",
            "fires_count": len(nearby),
            "newest": (
                max(f.acq_datetime for f in nearby).isoformat() if nearby else None
            ),
        }

    async def get_model_estimate(lat: float, lon: float) -> dict[str, Any]:
        from dhuan.api.routers.estimate import compute_estimate  # noqa: PLC0415

        result = await compute_estimate(lat, lon, get_settings())
        return {
            "ok": True,
            "summary": (
                f"estimated PM2.5 {result.pm25_mid} ug/m3 "
                f"[{result.pm25_low}, {result.pm25_high}] ({result.category})"
            ),
            "pm25_mid": result.pm25_mid,
            "pm25_low": result.pm25_low,
            "pm25_high": result.pm25_high,
            "category": result.category,
            "served_by": result.served_by,
        }

    async def get_station_context(lat: float, lon: float, radius_km: float = 10) -> dict[str, Any]:
        del radius_km  # station lookup does not need a radius
        outcome = await stations_near(lat, lon)
        nearest = nearest_reading(outcome.data or [], lat, lon)
        if nearest is None:
            return {"ok": False, "summary": "no station reading available"}
        reading, distance = nearest
        return {
            "ok": True,
            "summary": (
                f"nearest station {reading.name} at {distance:.1f} km reads "
                f"{reading.value:.0f} {reading.unit}"
            ),
            "station": reading.name,
            "station_pm25": reading.value,
            "distance_km": round(distance, 2),
            "data_age_seconds": round(reading.age_seconds(), 1),
        }

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="get_air_and_wind",
            description=(
                "Current hourly weather, especially wind speed and the meteorological "
                "wind-from direction, near a point. Use this first: wind decides "
                "which sources matter."
            ),
            parameters=_point_schema(),
            handler=get_air_and_wind,
        )
    )
    registry.register(
        ToolSpec(
            name="find_upwind_sources",
            description=(
                "Candidate pollution sources (landfill, industrial, construction, "
                "major junction) from OpenStreetMap within a radius, filtered to "
                "the upwind cone, each with a transparent influence score."
            ),
            parameters=_point_schema(),
            handler=find_upwind_sources,
        )
    )
    registry.register(
        ToolSpec(
            name="get_recent_fires",
            description=(
                "NASA FIRMS active-fire detections within a radius and the last "
                "few days. Returns an explicit unavailable result when not "
                "configured; never guesses."
            ),
            parameters=_point_schema(),
            handler=get_recent_fires,
        )
    )
    registry.register(
        ToolSpec(
            name="get_model_estimate",
            description=(
                "The PM2.5 model estimate with its 80% interval and which "
                "producer (model or nearest-station baseline) served it."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                },
                "required": ["lat", "lon"],
            },
            handler=get_model_estimate,
        )
    )
    registry.register(
        ToolSpec(
            name="get_station_context",
            description=(
                "The nearest official CPCB/OpenAQ station reading: value, distance "
                "and how old the reading is."
            ),
            parameters=_point_schema(),
            handler=get_station_context,
        )
    )
    return registry


__all__ = [
    "Evidence",
    "ToolRegistry",
    "ToolSpec",
    "default_registry",
    "new_evidence_id",
]
