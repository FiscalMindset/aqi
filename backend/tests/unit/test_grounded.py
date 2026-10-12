"""Tests for the grounded-explanation integration in /v1/explain.

These mock the tool evidence rather than calling out, so they exercise the
mapping and the fallback behaviour with no OpenAQ key required.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from dhuan.agents.grounded import evidence_gaps, grounded_answer


def _evidence(tool: str, ok: bool = True, **result: Any) -> dict[str, Any]:
    return {
        "evidence_id": f"ev-{tool}",
        "tool": tool,
        "args": {"lat": 28.6, "lon": 77.2},
        "summary": "",
        "fetched_at": "2026-10-12T09:00:00+00:00",
        "ok": ok,
        "note": None,
        "result": result if ok else None,
    }


def _estimate(**kw: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "pm25_mid": 220.0,
        "pm25_low": 200.0,
        "pm25_high": 240.0,
        "served_by": "model",
        "persistence_anchor_ugm3": 224.0,
        "model_adjustment_ugm3": -4.0,
        "data_age_seconds": 3600,
        "stale": False,
        "features_used": [],
    }
    base.update(kw)
    return SimpleNamespace(**base)


FULL_EVIDENCE = [
    _evidence(
        "get_station_context",
        station="R.K. Puram-DPCC",
        station_pm25=224.0,
        distance_km=1.9,
        data_age_seconds=3600,
        observed_at="2026-10-12T09:00:00+00:00",
    ),
    _evidence(
        "get_air_and_wind",
        wind_speed_ms=2.5,
        wind_from_deg=300,
        data_age_seconds=1800,
    ),
    _evidence(
        "find_upwind_sources",
        sources=[
            {
                "type": "landfill",
                "name": "Ghazipur",
                "distance_km": 9.5,
                "bearing_deg": 295,
                "influence_score": 0.7,
            }
        ],
        wind_from_deg=300,
    ),
    _evidence("get_recent_fires", fires_count=0),
]


def test_grounded_answer_composes_from_tool_evidence() -> None:
    answer = grounded_answer(
        evidence_items=FULL_EVIDENCE,
        estimate=_estimate(),
        query="why is it bad here?",
        model_accuracy={"mae": 11.12, "unseen_mae": 10.58},
    )
    body = answer.body
    assert "R.K. Puram" in body or "station" in body.lower()
    assert "Ghazipur" in body
    assert answer.paragraphs


def test_wind_from_direction_is_not_flipped() -> None:
    """A 'from' direction reversed would invert the whole attribution."""
    answer = grounded_answer(
        evidence_items=FULL_EVIDENCE,
        estimate=_estimate(),
        query="which way is the wind?",
    )
    wind = next(p for p in answer.paragraphs if p.intent == "which way the air is moving")
    assert "north-west" in wind.text or "northwest" in wind.text or "west" in wind.text


def test_sources_are_marked_upwind_because_the_tool_filters() -> None:
    answer = grounded_answer(
        evidence_items=FULL_EVIDENCE, estimate=_estimate(), query="what is upwind?"
    )
    upwind = next(p for p in answer.paragraphs if p.intent == "what is upwind of here")
    assert "upwind" in upwind.text
    assert "Ghazipur" in upwind.text


def test_passages_cite_the_tool_evidence_ids() -> None:
    answer = grounded_answer(
        evidence_items=FULL_EVIDENCE, estimate=_estimate(), query="explain"
    )
    cited = {p.evidence_id for p in answer.passages if p.evidence_id}
    assert "ev-get_station_context" in cited
    assert "ev-find_upwind_sources" in cited


def test_missing_station_tool_leaves_it_out_and_reports_the_gap() -> None:
    evidence = [e for e in FULL_EVIDENCE if e["tool"] != "get_station_context"]
    answer = grounded_answer(evidence_items=evidence, estimate=_estimate(), query="explain")
    assert not any(p.kind == "station_reading" for p in answer.passages)
    gaps = evidence_gaps(evidence)
    assert "nearby station reading" in gaps


def test_failed_tool_is_treated_as_missing_not_as_zero() -> None:
    """A failed station fetch must not become 'station measured 0'."""
    evidence = [
        e
        if e["tool"] != "get_station_context"
        else _evidence("get_station_context", ok=False)
        for e in FULL_EVIDENCE
    ]
    answer = grounded_answer(evidence_items=evidence, estimate=_estimate(), query="explain")
    assert not any(p.kind == "station_reading" for p in answer.passages)


def test_no_evidence_still_returns_a_truthful_answer() -> None:
    answer = grounded_answer(evidence_items=[], estimate=_estimate(), query="explain")
    assert answer.to_dict()["grounded"] is True
    # the estimate itself is still true and citable
    assert any(p.kind == "model_estimate" for p in answer.passages)
    assert all(p.passage_ids for p in answer.paragraphs)


def test_evidence_gaps_lists_what_did_not_answer() -> None:
    gaps = evidence_gaps([_evidence("get_air_and_wind", ok=False)])
    assert "current wind" in gaps
    assert "nearby station reading" in gaps  # never called
    assert "upwind sources" in gaps


def test_evidence_gaps_empty_when_all_answer() -> None:
    assert evidence_gaps(FULL_EVIDENCE) == []


def test_model_accuracy_is_woven_in_when_supplied() -> None:
    answer = grounded_answer(
        evidence_items=FULL_EVIDENCE,
        estimate=_estimate(),
        query="how much to trust it?",
        model_accuracy={"mae": 11.12, "unseen_mae": 10.58},
    )
    trust = next(p for p in answer.paragraphs if p.intent == "how much to trust it")
    assert "11.1" in trust.text
    assert "10.6" in trust.text
