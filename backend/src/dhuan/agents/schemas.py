"""Structured schemas for agent outputs (Pydantic v2).

Every claim in an attribution result references one or more evidence ids
produced by a tool call in the SAME run. The UI renders the trace.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
Band = Literal["High", "Medium", "Low"]


class EvidenceItem(BaseModel):
    """One tool result in the run that produced an explanation."""

    evidence_id: str
    tool: str
    args: dict[str, object]
    summary: str
    fetched_at: str
    ok: bool = True
    note: str | None = None


class LikelyCause(BaseModel):
    """A ranked candidate contributor, always labelled as a likely cause."""

    rank: int
    category: str  # source *category*: landfill, industrial, construction, ...
    label: str
    band: Band
    evidence_ids: list[str] = Field(min_length=1)
    reasoning: str
    distance_km: float | None = None
    bearing_deg: float | None = None


class AttributionResult(BaseModel):
    """Structured result from the attribution agent."""

    summary: str
    likely_causes: list[LikelyCause]
    confidence: Confidence
    confidence_reason: str
    evidence: list[EvidenceItem]
    tool_calls: list[str] = Field(default_factory=list)


class PersonaAdvice(BaseModel):
    persona: Literal["parent", "rider", "worker", "general"]
    headline: str
    actions: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default="General guidance for information only, not medical or legal advice."
    )


class AdvisoryResult(BaseModel):
    attribution: AttributionResult
    advice: list[PersonaAdvice]
    model_version: str


class ExplainResponse(BaseModel):
    """What POST /v1/explain returns."""

    lat: float
    lon: float
    estimate: dict[str, object]
    attribution: AttributionResult
    advice: list[PersonaAdvice]
