"""Turn one agent run's tool evidence into a grounded, cited answer.

This sits beside the agent rather than inside it, on purpose. The agent fetches
evidence; this reuses that evidence to compose prose. Nothing is fetched twice,
and if every tool failed we still get a truthful answer that says the inputs are
missing rather than an error or an invention.

The mapping between tool payloads and passages lives here, so the corpus builder
stays a pure function of already-normalised inputs.
"""

from __future__ import annotations

from typing import Any

from dhuan.agents.corpus import build_passages
from dhuan.agents.narrative import GroundedAnswer, compose
from dhuan.agents.retrieval import Passage

# tool name -> the corpus slot it fills
TOOL_STATION = "get_station_context"
TOOL_WEATHER = "get_air_and_wind"
TOOL_SOURCES = "find_upwind_sources"
TOOL_FIRES = "get_recent_fires"


def _ok(item: dict[str, Any]) -> dict[str, Any] | None:
    """The payload of an evidence item, or None if the tool did not succeed."""
    if not item.get("ok"):
        return None
    result = item.get("result")
    if not isinstance(result, dict):
        return None
    return result


def _evidence_ids(items: list[dict[str, Any]]) -> dict[str, str]:
    """Map each tool to the id of its successful evidence item, for citation."""
    ids: dict[str, str] = {}
    for item in items:
        tool = str(item.get("tool") or "")
        if tool in {TOOL_STATION, TOOL_WEATHER, TOOL_SOURCES, TOOL_FIRES} and item.get("ok"):
            ids[tool] = str(item.get("evidence_id") or "")
    return ids


def grounded_answer(
    *,
    evidence_items: list[dict[str, Any]],
    estimate: Any,
    query: str,
    model_accuracy: dict[str, Any] | None = None,
    language: str = "en",
) -> GroundedAnswer:
    """Compose a cited answer from evidence an agent run already collected."""
    by_tool = {
        str(item.get("tool") or ""): item
        for item in evidence_items
    }
    ids = _evidence_ids(evidence_items)

    # --- stations ---------------------------------------------------------
    stations: list[dict[str, Any]] = []
    station_payload = _ok(by_tool.get(TOOL_STATION, {}))
    if station_payload and station_payload.get("station_pm25") is not None:
        stations.append(
            {
                "name": station_payload.get("station"),
                "pm25": station_payload.get("station_pm25"),
                "distance_km": station_payload.get("distance_km"),
                "age_seconds": station_payload.get("data_age_seconds"),
                "observed_at": station_payload.get("observed_at"),
                "sensor_id": station_payload.get("sensor_id"),
            }
        )

    # --- sources ----------------------------------------------------------
    sources: list[dict[str, Any]] = []
    source_payload = _ok(by_tool.get(TOOL_SOURCES, {}))
    if source_payload:
        for hit in source_payload.get("sources") or []:
            if not isinstance(hit, dict):
                continue
            sources.append(
                {
                    **hit,
                    # this tool filters to the upwind cone already, so anything
                    # it returns is upwind by construction, not by guesswork
                    "in_upwind_cone": True,
                }
            )

    # --- weather ----------------------------------------------------------
    weather: dict[str, Any] | None = None
    weather_payload = _ok(by_tool.get(TOOL_WEATHER, {}))
    if weather_payload:
        wind_from = weather_payload.get("wind_from_deg")
        weather = {
            "wind_speed_ms": weather_payload.get("wind_speed_ms"),
            # the tool reports the meteorological "wind from" direction, which
            # is what decides which sources are upwind; do not flip it
            "wind_direction_deg": wind_from,
            "wind_gust_ms": weather_payload.get("wind_gust_ms"),
            "age_seconds": weather_payload.get("data_age_seconds"),
            "observed_at": weather_payload.get("observed_at"),
        }

    # --- fires ------------------------------------------------------------
    fires: int | None = None
    fire_payload = _ok(by_tool.get(TOOL_FIRES, {}))
    if fire_payload and fire_payload.get("fires_count") is not None:
        fires = int(fire_payload["fires_count"])

    passages: list[Passage] = build_passages(
        estimate=estimate,
        stations=stations,
        sources=sources,
        weather=weather,
        model_accuracy=model_accuracy,
        fires=fires,
        evidence_ids={
            "station": ids.get(TOOL_STATION, ""),
            "sources": ids.get(TOOL_SOURCES, ""),
            "fires": ids.get(TOOL_FIRES, ""),
        },
    )
    return compose(passages, query, language=language)


def evidence_gaps(evidence_items: list[dict[str, Any]]) -> list[str]:
    """Which tools did not answer, so the response can say so honestly."""
    gaps = []
    for tool, label in (
        (TOOL_STATION, "nearby station reading"),
        (TOOL_WEATHER, "current wind"),
        (TOOL_SOURCES, "upwind sources"),
    ):
        item = next(
            (i for i in evidence_items if str(i.get("tool")) == tool), None
        )
        if item is None or not item.get("ok"):
            gaps.append(label)
    return gaps


__all__ = ["evidence_gaps", "grounded_answer"]
