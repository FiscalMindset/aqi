"""Tests for the optional Groq fluency pass.

The product's promise is that the explanation works with no LLM at all. These
tests therefore care far more about the failure paths than the happy path: every
way Groq can break must land on the composed, grounded text.

Groq is mocked with respx; nothing here touches the network.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from dhuan.agents.rewrite import (
    introduces_new_numbers,
    is_usable,
    rewrite_explanation,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADLINE = "Estimated 223 µg/m³ here — Very Poor band, unhealthy for everyone."
BODY = (
    "We estimate 223 µg/m³ at this point, in the Very Poor band. The 80% range "
    "is 202 to 244 µg/m³. The nearest official monitor read 226 µg/m³ an hour "
    "earlier, and the model corrects it down by 2.6 µg/m³."
)
ORIGINAL = f"{HEADLINE} {BODY}"

PASSAGES = [
    {"kind": "model_estimate", "text": "Estimated 223 ug/m3, range 202-244"},
    {"kind": "station_reading", "text": "Station read 226 ug/m3"},
]


def _settings(**kw: object):
    from dhuan.core.config import Settings

    base: dict[str, object] = {
        "groq_api_key": "test-key",
        "groq_model": "openai/gpt-oss-120b",
        "groq_enabled": True,
        "groq_timeout_seconds": 5.0,
    }
    base.update(kw)
    return Settings(**base)  # type: ignore[arg-type]


def _completion(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


async def _run(settings: object) -> tuple[str, str]:
    return await rewrite_explanation(
        headline=HEADLINE,
        body=BODY,
        passages=PASSAGES,
        settings=settings,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------
# the guard
# --------------------------------------------------------------------------


def test_guard_catches_an_invented_number() -> None:
    assert introduces_new_numbers("it is 223 ug", "it is 223 ug, or maybe 310 ug")
    assert not introduces_new_numbers("it is 223 ug", "it is about 223 ug here")


def test_guard_treats_thousands_separators_as_equal() -> None:
    assert not introduces_new_numbers("1200 vehicles", "1,200 vehicles")


def test_usable_rejects_a_too_short_rewrite() -> None:
    assert not is_usable("Yes.", ORIGINAL)


def test_usable_rejects_a_refusal() -> None:
    assert not is_usable(
        "I cannot rewrite this text as it is a factual statement about air " * 2,
        ORIGINAL,
    )


def test_usable_rejects_an_apology_prefix() -> None:
    assert not is_usable("As an AI I am unable to help. " * 3, ORIGINAL)


def test_usable_rejects_rambling() -> None:
    assert not is_usable("blah " * 400, ORIGINAL)


def test_usable_accepts_a_clean_rewrite() -> None:
    good = (
        "The estimate here is 223 µg/m³, which places it in the Very Poor band. "
        "The 80% range runs from 202 to 244 µg/m³. The nearest official monitor "
        "recorded 226 µg/m³ an hour earlier, and the model adjusts that downward "
        "by 2.6 µg/m³."
    )
    assert is_usable(good, ORIGINAL)


# --------------------------------------------------------------------------
# happy path
# --------------------------------------------------------------------------


@respx.mock
async def test_a_good_rewrite_is_used() -> None:
    route = respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(
            "The estimate here is 223 µg/m³, placing it in the Very Poor band. "
            "The 80% range runs from 202 to 244 µg/m³. The nearest official "
            "monitor recorded 226 µg/m³ an hour earlier, and the model adjusts "
            "that downward by 2.6 µg/m³."
        ))
    )
    text, served = await _run(_settings())
    assert route.called
    assert served == "composed-grounded+groq"
    assert "The estimate here is 223" in text


@respx.mock
async def test_groq_receives_the_evidence_and_the_original() -> None:
    route = respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(ORIGINAL))
    )
    await _run(_settings())
    body = route.calls[0].request.content.decode()
    assert "station_reading" in body
    assert "Station read 226" in body
    assert "223" in body
    # the guard forbids inventing, and the prompt says so too
    assert "Never introduce a number" in body


# --------------------------------------------------------------------------
# every failure path must keep the composed text
# --------------------------------------------------------------------------


@respx.mock
async def test_no_api_key_skips_groq_entirely() -> None:
    route = respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(ORIGINAL))
    )
    text, served = await _run(_settings(groq_api_key=""))
    assert not route.called
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_disabled_groq_skips_the_call() -> None:
    route = respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(ORIGINAL))
    )
    text, served = await _run(_settings(groq_enabled=False))
    assert not route.called
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 502, 503])
async def test_any_http_error_keeps_the_composed_text(status: int) -> None:
    respx.post(GROQ_URL).mock(return_value=httpx.Response(status, json={"error": "no"}))
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_network_failure_keeps_the_composed_text() -> None:
    respx.post(GROQ_URL).mock(side_effect=httpx.ConnectError("dns failure"))
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_timeout_keeps_the_composed_text() -> None:
    respx.post(GROQ_URL).mock(side_effect=httpx.ReadTimeout("too slow"))
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_malformed_json_keeps_the_composed_text() -> None:
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_empty_choices_keeps_the_composed_text() -> None:
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json={"choices": []}))
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_null_content_keeps_the_composed_text() -> None:
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": None}}]})
    )
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert text == ORIGINAL


@respx.mock
async def test_an_invented_number_is_rejected() -> None:
    """The model 'helpfully' adds a station the user never asked about."""
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(
            "The estimate is 223 µg/m³, but the nearby station at Anand Vihar "
            "recorded 340 µg/m³, which is far worse than anything seen here."
        ))
    )
    text, served = await _run(_settings())
    assert served == "composed-grounded"
    assert "Anand Vihar" not in text
    assert "340" not in text
    assert text == ORIGINAL


@respx.mock
async def test_an_invented_recommendation_is_allowed_through_but_is_risky() -> None:
    """Documents the boundary: the numeric guard is what we rely on.

    A rewrite that adds advice without adding a number passes the guard. That is
    a known, accepted limit of the fluency pass, which is exactly why the
    composed text stays the audit trail and the paragraphs keep their citations.
    """
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(
            "At 223 µg/m³ in the Very Poor band, you should keep windows closed "
            "and wear a mask outdoors. The 80% range runs from 202 to 244 µg/m³ "
            "and the nearest official monitor recorded 226 µg/m³ an hour earlier."
        ))
    )
    text, served = await _run(_settings())
    assert served == "composed-grounded+groq"
    assert "mask" in text


@respx.mock
async def test_a_rewrite_of_the_identical_text_is_still_grounded() -> None:
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(ORIGINAL))
    )
    text, served = await _run(_settings())
    assert text == ORIGINAL
    assert served in {"composed-grounded", "composed-grounded+groq"}


@respx.mock
async def test_the_api_key_is_sent_as_a_bearer_token_and_not_logged() -> None:
    route = respx.post(GROQ_URL).mock(
        return_value=httpx.Response(200, json=_completion(ORIGINAL))
    )
    await _run(_settings(groq_api_key="sk-secret-value"))
    auth = route.calls[0].request.headers.get("authorization", "")
    assert auth == "Bearer sk-secret-value"
    # the key must never end up in the explanation we return
    assert "sk-secret" not in ORIGINAL


# --------------------------------------------------------------------------
# the end-to-end promise
# --------------------------------------------------------------------------


@respx.mock
async def test_the_explanation_survives_groq_being_completely_down() -> None:
    """The product's actual promise: no LLM, still a real explanation.

    Groq times out on every call. The composer still produces every paragraph,
    every paragraph is still cited, and the guard still passes.
    """
    from types import SimpleNamespace

    from dhuan.agents.corpus import build_passages
    from dhuan.agents.narrative import compose

    respx.post(GROQ_URL).mock(side_effect=httpx.ReadTimeout("groq is down"))

    estimate = SimpleNamespace(
        pm25_mid=223.4, pm25_low=202.5, pm25_high=244.3, served_by="model",
        persistence_anchor_ugm3=226.0, model_adjustment_ugm3=-2.6,
        data_age_seconds=21600, stale=False,
        features_used=[SimpleNamespace(name="station_lag24", contribution_ugm3=-10.3)],
    )
    passages = build_passages(
        estimate=estimate,
        stations=[{"name": "New Delhi-8118", "pm25": 226.0, "distance_km": 3.2,
                   "age_seconds": 21600, "observed_at": "2026-10-12T09:00:00+00:00"}],
        sources=[{"type": "landfill", "name": "Ghazipur", "distance_km": 11.2,
                  "bearing_deg": 292, "in_upwind_cone": True, "influence_score": 0.62}],
        weather={"wind_speed_ms": 3.2, "wind_direction_deg": 292},
        model_accuracy={"mae": 11.12, "unseen_mae": 10.58},
        fires=0,
    )
    answer = compose(passages, "why is the air bad here?")

    text, served = await rewrite_explanation(
        headline=answer.headline, body=answer.body,
        passages=[p.to_dict() for p in answer.passages], settings=_settings(),
    )

    assert served == "composed-grounded"
    assert text == f"{answer.headline} {answer.body}"
    # every fact still made it into the answer
    assert "Ghazipur" in text
    assert "223" in text
    assert "11.2" in text


@respx.mock
async def test_a_groq_rewrite_keeps_the_citations_intact() -> None:
    """Fluent prose must not break traceability."""
    from types import SimpleNamespace

    from dhuan.agents.corpus import build_passages
    from dhuan.agents.narrative import compose

    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=_completion(
        "Air here is poor, at about 223 µg/m³ in the Very Poor band, with an "
        "80% range of 202 to 244 µg/m³. The nearest monitor read 226 µg/m³ an "
        "hour earlier. Ghazipur landfill sits 11.2 km upwind of this point, "
        "which is why it matters here today."
    )))

    estimate = SimpleNamespace(
        pm25_mid=223.4, pm25_low=202.5, pm25_high=244.3, served_by="model",
        persistence_anchor_ugm3=226.0, model_adjustment_ugm3=-2.6,
        data_age_seconds=21600, stale=False, features_used=[],
    )
    passages = build_passages(
        estimate=estimate,
        stations=[{"name": "New Delhi-8118", "pm25": 226.0, "distance_km": 3.2,
                   "age_seconds": 21600, "observed_at": "2026-10-12T09:00:00+00:00"}],
        sources=[{"type": "landfill", "name": "Ghazipur", "distance_km": 11.2,
                  "bearing_deg": 292, "in_upwind_cone": True, "influence_score": 0.62}],
        weather=None, model_accuracy={"mae": 11.12}, fires=0,
    )
    answer = compose(passages, "explain this")
    before = len(answer.passages)

    text, served = await rewrite_explanation(
        headline=answer.headline, body=answer.body,
        passages=[p.to_dict() for p in answer.passages], settings=_settings(),
    )
    answer.apply_prose(text, served_by=served)

    assert served == "composed-grounded+groq"
    assert len(answer.passages) == before          # evidence untouched
    for para in answer.paragraphs:
        assert para.passage_ids                    # still cited
        assert set(para.passage_ids) <= {p.passage_id for p in answer.passages}
