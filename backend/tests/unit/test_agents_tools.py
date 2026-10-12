"""Agent assembly tests: tool registry, schema validation, explain wiring."""

from __future__ import annotations

from typing import Any

import pytest

from dhuan.agents.schemas import AttributionResult, LikelyCause, PersonaAdvice
from dhuan.agents.tools import ToolRegistry, default_registry, new_evidence_id
from dhuan.core.config import Settings


def test_default_registry_has_five_tools() -> None:
    registry = default_registry()
    names = {spec["name"] for spec in registry.specs()}
    assert names == {
        "get_air_and_wind",
        "find_upwind_sources",
        "get_recent_fires",
        "get_model_estimate",
        "get_station_context",
    }
    for spec in registry.specs():
        assert spec["description"]
        assert spec["parameters"]["type"] == "object"


def test_evidence_items_summarize() -> None:
    registry = ToolRegistry()

    async def handler(**_kw: Any) -> Any:
        return {"summary": "wind 3 m/s from 292", "ok": True}

    from dhuan.agents.tools import ToolSpec

    registry.register(
        ToolSpec(
            name="t",
            description="d",
            parameters={"type": "object", "properties": {}},
            handler=handler,
        )
    )
    import asyncio

    evidence = asyncio.run(registry.run("t", {}))
    assert evidence.ok
    items = registry.evidence_items()
    assert items[0]["summary"] == "wind 3 m/s from 292"
    assert items[0]["evidence_id"] == evidence.evidence_id


def test_attribution_result_requires_evidence_on_claims() -> None:
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        LikelyCause(
            rank=1,
            category="landfill",
            label="L",
            band="High",
            evidence_ids=[],
            reasoning="r",
        )


def test_attribution_result_roundtrip() -> None:
    result = AttributionResult(
        summary="s",
        likely_causes=[],
        confidence="low",
        confidence_reason="r",
        evidence=[],
    )
    assert result.tool_calls == []


def test_persona_advice_has_default_disclaimer() -> None:
    advice = PersonaAdvice(
        persona="parent", headline="h", actions=["a"], evidence_ids=[]
    )
    assert "not medical" in advice.disclaimer


def test_build_agent_uses_scripted_backend_without_model_id() -> None:
    from dhuan.agents.attribution import build_agent

    settings = Settings(env="test", bedrock_model_id="")
    agent, served_by = build_agent(settings)
    assert served_by == "scripted-deterministic"
    assert agent.backend.served_by == "scripted-deterministic"


def test_new_evidence_id_unique() -> None:
    ids = {new_evidence_id() for _ in range(100)}
    assert len(ids) == 100
