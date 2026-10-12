"""Tests for the corpus builder and the LLM-free grounded composer.

The property that matters here is not the wording, it is that nothing can be
said without evidence. These tests attack that property directly.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from dhuan.agents.corpus import CPCB_BAND_TEXT, build_passages, compass, source_name
from dhuan.agents.narrative import GroundingError, compose
from dhuan.agents.retrieval import Passage

# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _estimate(**kw: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "pm25_mid": 223.4,
        "pm25_low": 202.5,
        "pm25_high": 244.3,
        "served_by": "model",
        "persistence_anchor_ugm3": 226.0,
        "model_adjustment_ugm3": -2.6,
        "data_age_seconds": 6 * 3600,
        "stale": False,
        "features_used": [
            SimpleNamespace(name="station_lag24", contribution_ugm3=-10.3),
            SimpleNamespace(name="wind_dir_cos", contribution_ugm3=4.4),
            SimpleNamespace(name="temp_c", contribution_ugm3=0.1),
        ],
    }
    base.update(kw)
    return SimpleNamespace(**base)


STATIONS: list[dict[str, Any]] = [
    {
        "name": "New Delhi-8118",
        "pm25": 226.0,
        "distance_km": 3.2,
        "age_seconds": 6 * 3600,
        "observed_at": "2026-10-12T09:00:00+00:00",
        "sensor_id": 8118,
    }
]

SOURCES: list[dict[str, Any]] = [
    {
        "type": "landfill",
        "name": "Ghazipur landfill",
        "distance_km": 11.2,
        "bearing_deg": 292,
        "in_upwind_cone": True,
        "influence_score": 0.62,
        "osm_id": "way/12345",
    },
    {
        "type": "major_junction",
        "name": "",
        "distance_km": 1.4,
        "bearing_deg": 180,
        "in_upwind_cone": False,
        "influence_score": 0.30,
    },
]

WEATHER: dict[str, Any] = {
    "wind_speed_ms": 3.2,
    "wind_direction_deg": 292,
    "wind_gust_ms": 5.1,
    "age_seconds": 1800,
}

ACCURACY: dict[str, Any] = {"mae": 11.12, "unseen_mae": 10.58}


def _passages(**kw: Any) -> list[Passage]:
    args: dict[str, Any] = {
        "estimate": _estimate(),
        "stations": STATIONS,
        "sources": SOURCES,
        "weather": WEATHER,
        "model_accuracy": ACCURACY,
        "fires": 0,
    }
    args.update(kw)
    return build_passages(**args)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# compass
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("deg", "expected"),
    [
        (0.0, "north"),
        (11.0, "north"),
        (90.0, "east"),
        (180.0, "south"),
        (270.0, "west"),
        (292.0, "west-northwest"),
        (359.0, "north"),
        (-90.0, "west"),
        (720.0, "north"),
        (45.0, "northeast"),
    ],
)
def test_compass_renders_words(deg: float, expected: str) -> None:
    assert compass(deg) == expected


def test_compass_handles_missing_direction() -> None:
    assert compass(None) == "unknown direction"


def test_compass_never_returns_degrees() -> None:
    """People read this text; degrees are useless to them."""
    for deg in range(0, 360, 7):
        assert not any(ch.isdigit() for ch in compass(float(deg)))


# --------------------------------------------------------------------------
# source naming
# --------------------------------------------------------------------------


def test_source_name_uses_a_real_name() -> None:
    assert source_name({"name": "Ghazipur landfill"}, "landfill") == "Ghazipur landfill"


def test_source_name_falls_back_when_the_name_is_the_type() -> None:
    assert source_name({"name": "landfill"}, "landfill") == "landfill"
    assert source_name({"name": ""}, "major_junction") == "major junction"
    assert source_name({"name": "unknown"}, "industrial") == "industrial site"


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------


def test_station_reading_is_marked_as_measured_and_highest_authority() -> None:
    ps = _passages()
    station = next(p for p in ps if p.kind == "station_reading")
    assert station.measured is True
    assert station.authority == max(p.authority for p in ps)
    assert "measured" in station.text
    assert "226" in station.text


def test_estimate_is_not_marked_as_measured() -> None:
    """The most important distinction in the whole product."""
    ps = _passages()
    estimate = next(p for p in ps if p.kind == "model_estimate")
    assert estimate.measured is False
    assert "estimate" in estimate.text.lower()


def test_every_passage_kind_has_a_human_label() -> None:
    ps = _passages()
    for p in ps:
        assert p.text.strip()
        assert not p.text.strip().endswith(":")


def test_cpcb_band_is_included_with_its_table_version() -> None:
    ps = _passages()
    band = next(p for p in ps if p.kind == "cpcb_band")
    assert "Very Poor" in band.text
    assert "2014-11-24h-breaks" in band.text


def test_parameters_below_half_a_unit_are_dropped_as_noise() -> None:
    ps = _passages()
    names = {p.facts.get("name") for p in ps if p.kind == "model_parameters"}
    assert "temp_c" not in names
    assert "station_lag24" in names


def test_source_passages_split_upwind_from_nearby() -> None:
    ps = _passages()
    upwind = [p for p in ps if p.kind == "source_upwind"]
    nearby = [p for p in ps if p.kind == "source_nearby"]
    assert len(upwind) == 1
    assert len(nearby) == 1
    assert upwind[0].facts["name"] == "Ghazipur landfill"
    assert "upwind" in upwind[0].text


def test_source_without_a_name_does_not_say_a_useless_name() -> None:
    ps = _passages()
    nearby = next(p for p in ps if p.kind == "source_nearby")
    assert "major junction" in nearby.text
    assert "—  " not in nearby.text


def test_ventilation_is_a_separate_derived_passage() -> None:
    """Ventilation is inferred from wind; it must not look like a measurement."""
    ps = _passages()
    kinds = {p.kind for p in ps}
    assert "wind" in kinds
    assert "ventilation" in kinds
    vent = next(p for p in ps if p.kind == "ventilation")
    assert vent.measured is False
    assert vent.authority < next(p for p in ps if p.kind == "wind").authority


@pytest.mark.parametrize(
    ("speed", "gust", "verdict"),
    [
        (0.8, None, "poor"),
        (3.0, None, "moderate"),
        (5.0, None, "good"),
        (2.0, 9.0, "good"),
    ],
)
def test_ventilation_thresholds(speed: float, gust: float | None, verdict: str) -> None:
    ps = _passages(weather={"wind_speed_ms": speed, "wind_direction_deg": 10, "wind_gust_ms": gust})
    vent = next(p for p in ps if p.kind == "ventilation")
    assert f"is {verdict}" in vent.text


def test_no_ventilation_passage_without_wind() -> None:
    ps = _passages(weather=None)
    assert not [p for p in ps if p.kind == "ventilation"]


def test_freshness_passage_states_the_age_and_staleness() -> None:
    ps = _passages()
    fresh = next(p for p in ps if p.kind == "freshness")
    assert "6 hours old" in fresh.text
    assert "stale" not in fresh.text


def test_stale_inputs_are_said_out_loud() -> None:
    ps = _passages(estimate=_estimate(stale=True))
    fresh = next(p for p in ps if p.kind == "freshness")
    assert "stale" in fresh.text


def test_nearest_station_fallback_is_explained_not_hidden() -> None:
    ps = _passages(estimate=_estimate(served_by="nearest-station", persistence_anchor_ugm3=None))
    est = next(p for p in ps if p.kind == "model_estimate")
    assert "model could not be used" in est.text


def test_trend_is_derived_from_readings_we_hold() -> None:
    ps = _passages(
        stations=[
            {"name": "S-1", "pm25": 240.0, "observed_at": "2026-10-12T09:00:00+00:00"},
            {"name": "S-1", "pm25": 200.0, "observed_at": "2026-10-12T06:00:00+00:00"},
        ]
    )
    trend = next(p for p in ps if p.kind == "station_trend")
    assert trend.facts["delta"] == 40.0
    assert trend.facts["hours"] == 3
    assert "higher" in trend.text


def test_no_trend_without_two_readings() -> None:
    ps = _passages(stations=[])
    assert not [p for p in ps if p.kind == "station_trend"]


def test_trend_needs_real_timestamps() -> None:
    ps = _passages(
        stations=[
            {"name": "S-1", "pm25": 240.0, "observed_at": None},
            {"name": "S-1", "pm25": 200.0, "observed_at": None},
        ]
    )
    assert not [p for p in ps if p.kind == "station_trend"]


def test_station_passages_link_to_cpcb_when_the_id_is_usable() -> None:
    ps = _passages()
    station = next(p for p in ps if p.kind == "station_reading")
    assert station.source_url is not None
    assert "cpcb.nic.in" in station.source_url


def test_source_passages_link_to_openstreetmap_for_real_ids() -> None:
    ps = _passages()
    upwind = next(p for p in ps if p.kind == "source_upwind")
    assert upwind.source_url == "https://www.openstreetmap.org/way/12345"


def test_static_source_ids_get_no_fabricated_link() -> None:
    ps = _passages(
        sources=[{**SOURCES[0], "osm_id": "static-ghazipur"}, {**SOURCES[1], "osm_id": None}]
    )
    for p in ps:
        if p.kind.startswith("source"):
            assert p.source_url is None


def test_fire_count_zero_says_nothing_is_burning() -> None:
    ps = _passages(fires=0)
    fires = next(p for p in ps if p.kind == "fire_activity")
    assert "No satellite fire detections" in fires.text
    assert fires.facts["count"] == 0


def test_no_optional_inputs_still_produces_a_usable_corpus() -> None:
    """Worst case: no stations, no sources, no weather. Must still answer."""
    ps = _passages(stations=[], sources=[], weather=None, model_accuracy=None, fires=None)
    kinds = {p.kind for p in ps}
    assert "model_estimate" in kinds
    assert "cpcb_band" in kinds
    assert "freshness" in kinds
    answer = compose(ps, "how bad is the air here?")
    assert answer.headline
    assert answer.paragraphs


# --------------------------------------------------------------------------
# composer
# --------------------------------------------------------------------------


def test_composer_answers_without_any_llm() -> None:
    answer = compose(_passages(), "why is the air bad on my street?")
    assert answer.served_by == "retrieval-grounded"
    assert answer.to_dict()["grounded"] is True
    assert len(answer.paragraphs) >= 6


def test_composer_cites_only_retrieved_passages() -> None:
    answer = compose(_passages(), "what is polluting this street?")
    retrieved = {p.passage_id for p in answer.passages}
    for para in answer.paragraphs:
        assert para.passage_ids
        assert set(para.passage_ids) <= retrieved


def test_every_paragraph_is_traceable() -> None:
    answer = compose(_passages(), "explain this to me")
    trace = {t["passage_id"] for t in answer.trace}
    for para in answer.paragraphs:
        assert set(para.passage_ids) <= trace


def test_composer_does_not_repeat_the_type_as_the_name() -> None:
    answer = compose(_passages(), "what is upwind?")
    text = answer.body
    assert "landfill — landfill" not in text
    assert "landfill —" not in text


def test_upwind_answer_names_the_upwind_source() -> None:
    answer = compose(_passages(), "what is upwind of my house?")
    upwind = next(p for p in answer.paragraphs if p.intent == "what is upwind of here")
    assert "Ghazipur" in upwind.text
    assert "11.2 km" in upwind.text


def test_downwind_source_is_never_claimed_as_the_cause() -> None:
    answer = compose(_passages(), "what is upwind of my house?")
    upwind = next(p for p in answer.paragraphs if p.intent == "what is upwind of here")
    assert "major junction" not in upwind.text


def test_when_nothing_is_upwind_the_answer_says_so() -> None:
    """Attribution must be allowed to come back empty."""
    answer = compose(_passages(sources=[SOURCES[1]]), "what is upwind?")
    assert any("No source was upwind" in p.text for p in answer.paragraphs)


def test_parameter_paragraph_disclaims_causation() -> None:
    answer = compose(_passages(), "why is the number what it is?")
    params = next(p for p in answer.paragraphs if p.intent == "what moved that estimate")
    assert "not proof of cause" in params.text


def test_estimate_paragraph_states_the_interval() -> None:
    answer = compose(_passages(), "how bad is it?")
    est = next(p for p in answer.paragraphs if p.intent == "what we estimate here")
    assert "202" in est.text and "244" in est.text
    assert "80% range" in est.text


def test_nearest_station_fallback_is_disclosed_to_the_user() -> None:
    answer = compose(
        _passages(estimate=_estimate(served_by="nearest-station", persistence_anchor_ugm3=None)),
        "how bad is it?",
    )
    est = next(p for p in answer.paragraphs if p.intent == "what we estimate here")
    assert "could not be used" in est.text


def test_headline_names_the_band() -> None:
    answer = compose(_passages(), "how bad is it?")
    assert "Very Poor" in answer.headline


def test_headline_reflects_a_clean_air_point() -> None:
    answer = compose(
        _passages(estimate=_estimate(pm25_mid=18.0, pm25_low=12.0, pm25_high=24.0)),
        "how bad is it?",
    )
    assert "Good" in answer.headline
    assert "unhealthy" not in answer.headline


def test_composer_survives_a_total_evidence_blackout() -> None:
    answer = compose([], "why is the air bad?")
    assert answer.paragraphs == []
    assert "0" in answer.headline or answer.headline


def test_grounding_guard_rejects_a_citation_it_cannot_find() -> None:
    from dhuan.agents.narrative import Paragraph, assert_grounded

    bogus = Paragraph("x", "text", ["not-retrieved"])
    with pytest.raises(GroundingError):
        assert_grounded([bogus], [Passage("real", "model_estimate", "t")])


def test_grounding_guard_rejects_an_uncited_paragraph() -> None:
    from dhuan.agents.narrative import Paragraph, assert_grounded

    with pytest.raises(GroundingError):
        assert_grounded([Paragraph("x", "text", [])], [])


def test_grounding_guard_rejects_advice_language() -> None:
    from dhuan.agents.narrative import Paragraph, assert_grounded

    p = Passage("real", "model_estimate", "t")
    cheeky = Paragraph("x", "You should wear a mask.", ["real"])
    with pytest.raises(GroundingError):
        assert_grounded([cheeky], [p])


def test_the_forbidden_advice_phrases_are_really_forbidden() -> None:
    from dhuan.agents.narrative import FORBIDDEN_UNGROUNDED

    for phrase in ("you should", "we recommend", "studies show", "in my opinion"):
        assert FORBIDDEN_UNGROUNDED.search(f"I think {phrase} this is fine")


def test_a_single_fact_only_corpus_still_composes() -> None:
    lone = [Passage("only", "freshness", "The inputs are 1 hour old.", authority=0.9)]
    answer = compose(lone, "is this current?")
    assert answer.paragraphs
    assert answer.paragraphs[0].passage_ids == ["only"]


def test_band_text_covers_every_cpcb_category() -> None:
    assert set(CPCB_BAND_TEXT) == {
        "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe",
    }
