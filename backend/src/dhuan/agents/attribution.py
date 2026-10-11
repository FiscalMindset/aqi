"""Attribution + advisory agents: the /v1/explain entry point."""

from __future__ import annotations

from typing import Any

from dhuan.agents.guardrails import SYSTEM_PREAMBLE
from dhuan.agents.runtime import AttributionAgent, BedrockBackend, ScriptedBackend
from dhuan.agents.schemas import PersonaAdvice
from dhuan.agents.tools import default_registry
from dhuan.api.errors import outside_coverage_problem
from dhuan.api.routers.estimate import estimate as estimate_route
from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.core.metrics import record
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.model.cpcb import category_for_pm25

logger = get_logger("agents.explain")

ATTRIBUTION_SYSTEM = (
    "You are Dhuan Detective's attribution analyst for Delhi-NCR. "
    "Call tools first (station, weather/wind, model estimate, upwind sources, "
    "fires), then return ONLY a JSON object with keys: summary, likely_causes "
    "(rank, category, label, band High/Medium/Low, evidence_ids, reasoning), "
    "confidence (high/medium/low), confidence_reason. Every claim must cite "
    "tool evidence ids from this run. Name only source categories and mapped "
    "OSM sites. Use hedged language: likely, consistent with."
)

ADVISORY_SYSTEM = (
    "You are Dhuan Detective's advisory agent. Given a structured attribution "
    "and an estimate, write conservative, non-medical advice for three "
    "personas: parent (school-age children), rider (delivery riders on "
    "two-wheelers), worker (outdoor workers). Each item has: headline, 2-4 "
    "actions, evidence_ids used. Never give medical advice; add the disclaimer."
)


def build_agent(settings: Settings) -> tuple[AttributionAgent, str]:
    """Agent + its served_by label, choosing the backend from settings.

    Real Bedrock when configured; deterministic scripted backend otherwise
    (CI, DEMO, local dev) with identical tools and evidence rules.
    """
    registry = default_registry()
    if settings.bedrock_model_id:
        try:
            agent = AttributionAgent(registry, BedrockBackend(settings))
        except Exception as exc:
            logger.warning("bedrock_backend_unavailable: %s", exc)
            record("AgentBedrockFallback", 1)
        else:
            return agent, agent.backend.served_by
    return AttributionAgent(registry, ScriptedBackend()), "scripted-deterministic"


PERSONA_PROMPTS = {
    "parent": "parent with school-age children",
    "rider": "delivery rider on a two-wheeler",
    "worker": "outdoor worker",
}


def advice_for_attribution(
    attribution: Any, estimate: dict[str, Any]
) -> list[PersonaAdvice]:
    """Advisory synthesis from the attribution (deterministic).

    Conservative wording by construction: no medical claims, always the
    general-guidance disclaimer, always evidence-linked.
    """
    category = str(estimate.get("category", "Unknown"))
    pm25 = float(estimate.get("pm25_mid") or 0.0)
    top = attribution.likely_causes[0].label if attribution.likely_causes else None
    evidence_ids = [c.evidence_ids[0] for c in attribution.likely_causes if c.evidence_ids]

    def base_headline(who: str) -> str:
        if category in ("Severe", "Very Poor"):
            return f"Air is {category.lower()} ({pm25:.0f} µg/m³): {who} should limit outdoor time"
        if category == "Poor":
            return f"Air is poor ({pm25:.0f} µg/m³): {who} should reduce strenuous time"
        if category == "Moderately Polluted":
            return f"Air is moderately polluted ({pm25:.0f} µg/m³): {who} should watch symptoms"
        return f"Air is {category.lower()} ({pm25:.0f} µg/m³): normal activity is reasonable"

    return [
        PersonaAdvice(
            persona="parent",
            headline=base_headline("children"),
            actions=[
                "Keep outdoor play short and close to home during peak hours",
                "Prefer mornings or after rain when levels are usually lower"
                if category in ("Poor", "Very Poor", "Severe")
                else "Normal play is reasonable; keep an eye on how children feel",
                "A well-fitted mask outdoors helps on bad-air days"
                if category in ("Poor", "Very Poor", "Severe")
                else "No special precautions needed at this level",
            ],
            evidence_ids=evidence_ids[:2],
        ),
        PersonaAdvice(
            persona="rider",
            headline=base_headline("delivery riders"),
            actions=[
                "Use the cleanest-route comparison to reduce time in the worst pockets",
                "Take breaks indoors or in shaded areas during peak pollution"
                if category in ("Poor", "Very Poor", "Severe")
                else "Stay hydrated and take normal breaks",
                "Wear a mask on high-traffic stretches"
                if category in ("Poor", "Very Poor", "Severe")
                else "Standard riding precautions apply",
            ],
            evidence_ids=evidence_ids[:2],
        ),
        PersonaAdvice(
            persona="worker",
            headline=base_headline("outdoor workers"),
            actions=[
                "Schedule heavy work for cooler, calmer-wind hours where possible",
                "Rotate strenuous tasks and rest in cleaner areas"
                if category in ("Poor", "Very Poor", "Severe")
                else "Normal work is reasonable at this level",
                "Employers should watch for staff discomfort on bad-air days"
                if category in ("Poor", "Very Poor", "Severe")
                else "No special arrangements needed",
            ],
            evidence_ids=evidence_ids[:2],
        ),
        PersonaAdvice(
            persona="general",
            headline=base_headline("everyone"),
            actions=[
                "Check the estimate and data age before planning outdoor time",
                (f"Likely contributor: {top}" if top else "No contributor stands out"),
            ],
            evidence_ids=evidence_ids[:2],
        ),
    ]


async def explain(
    lat: float, lon: float, settings: Settings | None = None
) -> tuple[Any, list[PersonaAdvice], str]:
    """Run attribution + advisory for a point; returns (result, advice, served_by)."""
    s = settings or get_settings()
    point = Point(lat=lat, lon=lon)
    if not point_in_ncr(point):
        raise outside_coverage_problem(lat, lon)

    agent, served_by = build_agent(s)
    result = await agent.run(lat, lon, system=f"{SYSTEM_PREAMBLE}\n\n{ATTRIBUTION_SYSTEM}")
    estimate_obj = await estimate_route(lat, lon, s)
    estimate = {
        "pm25_mid": estimate_obj.pm25_mid,
        "pm25_low": estimate_obj.pm25_low,
        "pm25_high": estimate_obj.pm25_high,
        "category": category_for_pm25(estimate_obj.pm25_mid),
        "served_by": estimate_obj.served_by,
        "model_version": estimate_obj.model_version,
        "data_age_seconds": estimate_obj.data_age_seconds,
        "demo_mode": estimate_obj.demo_mode,
    }
    advice = advice_for_attribution(result, estimate)
    record("AgentRuns", 1)
    if result.confidence == "low":
        record("AgentLowConfidence", 1)
    return result, advice, served_by


__all__ = [
    "ADVISORY_SYSTEM",
    "ATTRIBUTION_SYSTEM",
    "advice_for_attribution",
    "build_agent",
    "explain",
]
