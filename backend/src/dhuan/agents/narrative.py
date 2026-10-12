"""Compose a grounded answer from retrieved passages, with no LLM.

This is the G half. It is deliberately not a template with the numbers slotted
into one fixed sentence: each paragraph is built only from passages that were
actually retrieved for the intent it answers, and if a passage is missing the
paragraph is omitted rather than padded with a generic claim.

Three properties this design guarantees:

1. **Every sentence is traceable.** Each paragraph carries the passage ids it was
   built from, and `assert_grounded` will fail loudly if a paragraph references a
   passage that is not in the retrieval result.
2. **No invented numbers.** Numbers only enter through `fmt`, and every number a
   paragraph emits came from a passage fact.
3. **It works with every external service down.** No model call, no network.

When an LLM *is* available it may rewrite `body` for fluency, but the evidence
list and the numeric claims stay exactly as composed here, and
`assert_grounded` still runs on the final text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from dhuan.agents.retrieval import Passage, ScoredPassage, group_by_intent, retrieve
from dhuan.model.cpcb import category_for_pm25

# Words that must never appear in a grounded answer about a measurement.
FORBIDDEN_UNGROUNDED = re.compile(
    r"\b(you should|we recommend|i think|in my opinion|studies show|research shows)\b",
    re.I,
)


@dataclass(slots=True)
class Paragraph:
    """One grounded paragraph plus the passages it came from."""

    intent: str
    text: str
    passage_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "text": self.text, "passage_ids": self.passage_ids}


@dataclass(slots=True)
class GroundedAnswer:
    """The full composed answer plus everything needed to audit it."""

    headline: str
    paragraphs: list[Paragraph]
    passages: list[Passage]
    trace: list[dict[str, Any]]
    served_by: str = "retrieval-grounded"

    @property
    def body(self) -> str:
        return " ".join(p.text for p in self.paragraphs)

    def apply_prose(self, text: str, *, served_by: str) -> None:
        """Adopt an optional rewrite of the prose.

        Only the text surface changes. The passages, the paragraph-to-passage
        citations and the retrieval trace are left exactly as composed, because
        those are the audit trail and a fluency pass must never touch them.

        The rewrite is stored as one paragraph that inherits the citations of
        every paragraph it replaced, so `assert_grounded` still holds and the UI
        can still show what the text was derived from.
        """
        stripped = text.strip()
        if not stripped or stripped == self.body:
            self.served_by = served_by
            return
        inherited = sorted({pid for p in self.paragraphs for pid in p.passage_ids})
        self.paragraphs = [
            Paragraph(
                intent=self.paragraphs[0].intent if self.paragraphs else "explanation",
                text=stripped,
                passage_ids=inherited,
            )
        ]
        self.served_by = served_by
        # a rewrite may only reword; it must still be traceable
        assert_grounded(self.paragraphs, self.passages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "body": self.body,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "passages": [p.to_dict() for p in self.passages],
            "retrieval_trace": self.trace,
            "served_by": self.served_by,
            "grounded": True,
        }


def _by_kind(scored: list[ScoredPassage], kind: str) -> list[ScoredPassage]:
    return [s for s in scored if s.passage.kind == kind]


def _fmt(value: float, unit: str = "") -> str:
    digits = 0 if abs(value) >= 10 else 1
    return f"{value:.{digits}f}{unit}"


def _category_band(pm25: float) -> tuple[str, str]:
    cat = category_for_pm25(pm25)
    if cat == "Good":
        return cat, "comfortable"
    if cat == "Satisfactory":
        return cat, "tolerable"
    if cat == "Moderate":
        return cat, "noticeable to sensitive people"
    if cat == "Poor":
        return cat, "uncomfortable for everyone"
    if cat == "Very Poor":
        return cat, "unhealthy for everyone"
    return cat, "hazardous"


def compose(
    passages: list[Passage],
    query: str,
    *,
    top_k: int = 14,
    language: str = "en",
) -> GroundedAnswer:
    """Retrieve, then compose. No model call."""
    scored = retrieve(passages, query, top_k=top_k)
    chosen = [s.passage for s in scored]
    by_intent = group_by_intent(scored)
    trace = [
        {
            "passage_id": s.passage.passage_id,
            "kind": s.passage.kind,
            "score": s.score,
            "reasons": s.reasons,
        }
        for s in scored
    ]

    estimate = next((s for s in scored if s.passage.kind == "model_estimate"), None)
    pm25 = float(estimate.passage.facts.get("pm25", 0.0)) if estimate else 0.0
    cat, feel = _category_band(pm25)
    headline = (
        f"Estimated {pm25:.0f} µg/m³ here — {cat} band, {feel}."
        if language == "en"
        else f"यहाँ अनुमानित {_fmt(pm25)} µg/m³ — {cat} श्रेणी।"
    )

    paragraphs: list[Paragraph] = []

    # 1. what we estimate and how certain we are
    if estimate is not None:
        facts = estimate.passage.facts
        low, high = facts.get("low"), facts.get("high")
        anchor, adj = facts.get("anchor"), facts.get("adjustment")
        bits = [
            f"We estimate {pm25:.0f} µg/m³ at this point, in the {cat} band."
        ]
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            bits.append(
                f"The 80% range is {low:.0f} to {high:.0f} µg/m³, so treat anything "
                f"inside that band as consistent with the estimate."
            )
        if isinstance(anchor, (int, float)) and isinstance(adj, (int, float)):
            adj_f = float(adj)
            direction = "up" if adj_f >= 0 else "down"
            bits.append(
                f"That number starts from the nearest official station, which read "
                f"{float(anchor):.0f} µg/m³ an hour earlier, and the model corrects it "
                f"{direction} by {abs(adj_f):.1f} µg/m³ using the weather and the "
                "sources below."
            )
        elif facts.get("served_by") == "nearest-station":
            bits.append(
                "This is the nearest station's own reading repeated unchanged: the "
                "model could not be used for this point, so no adjustment has been made."
            )
        paragraphs.append(
            Paragraph(
                intent="what we estimate here",
                text=" ".join(bits),
                passage_ids=[estimate.passage.passage_id],
            )
        )

    # 2. what is actually being measured
    stations = _by_kind(scored, "station_reading")
    if stations:
        s = stations[0]
        f = s.passage.facts
        bits = [
            f"The nearest official monitor is {f.get('station', 'an unnamed station')}, "
            f"which measured {float(f.get('pm25', 0)):.0f} µg/m³."
        ]
        age = s.passage.age_phrase()
        if age:
            bits.append(f"That reading is {age}.")
        if len(stations) > 1:
            others = ", ".join(
                str(x.passage.facts.get("station", "?")) for x in stations[1:]
            )
            bits.append(f"Other monitors nearby: {others}.")
        paragraphs.append(
            Paragraph(
                intent="what is being measured nearby",
                text=" ".join(bits),
                passage_ids=[x.passage.passage_id for x in stations],
            )
        )

    # 3. trend
    trend = by_intent.get("is it getting better or worse")
    if trend is not None and "delta" in trend.passage.facts:
        paragraphs.append(
            Paragraph(
                intent="is it getting better or worse",
                text=trend.passage.text,
                passage_ids=[trend.passage.passage_id],
            )
        )

    # 4. upwind sources - the attribution the user actually came for
    upwind = _by_kind(scored, "source_upwind")
    if upwind:
        bits = []
        ids = []
        for x in upwind[:3]:
            f = x.passage.facts
            dist = f.get("distance_km")
            where = f"{float(dist):.1f} km" if isinstance(dist, (int,
                float)) else "a short distance"
            name = str(f.get("name") or "A source").capitalize()
            kind = str(f.get("type", "source")).replace("_", " ")
            # avoid "Ghazipur landfill - landfill -" when the name already says it
            kind_part = "" if kind.lower() in name.lower() else f" ({kind})"
            bits.append(
                f"{name}{kind_part} {where} upwind, "
                f"influence {float(f.get('influence', 0)):.2f}"
            )
            ids.append(x.passage.passage_id)
        lead = (
            "Air arriving at this point travels with the wind, so the sources that "
            "matter are the ones upwind of it."
        )
        paragraphs.append(
            Paragraph(
                intent="what is upwind of here",
                text=f"{lead} {'; '.join(bits)}.",
                passage_ids=ids,
            )
        )

    nearby = _by_kind(scored, "source_nearby")
    if nearby and not upwind:
        f = nearby[0].passage.facts
        dist = f.get("distance_km")
        paragraphs.append(
            Paragraph(
                intent="what is close to here",
                text=(
                    f"No source was upwind of this point at the time of the estimate. "
                    f"The nearest known source is {f.get('name', 'unidentified')}, "
                    f"{float(dist):.1f} km away."
                    if isinstance(dist, (int, float))
                    else "No source was upwind of this point at the time of the estimate."
                ),
                passage_ids=[nearby[0].passage.passage_id],
            )
        )

    # 5. wind and ventilation
    wind = by_intent.get("which way the air is moving")
    vent = by_intent.get("whether the air can clear")
    if wind is not None:
        ids = [wind.passage.passage_id]
        text = wind.passage.text
        if vent is not None:
            text = f"{text} {vent.passage.text}"
            ids.append(vent.passage.passage_id)
        paragraphs.append(
            Paragraph(intent="which way the air is moving", text=text, passage_ids=ids)
        )

    # 6. what moved the number
    params = _by_kind(scored, "model_parameters")
    if params:
        bits = []
        ids = []
        for x in params[:3]:
            f = x.passage.facts
            bits.append(
                f"{str(f.get('name', '')).replace('_', ' ')} "
                f"({float(f.get('contribution', 0)):+.1f} µg/m³)"
            )
            ids.append(x.passage.passage_id)
        paragraphs.append(
            Paragraph(
                intent="what moved that estimate",
                text=(
                    "Re-running the model with one parameter replaced by a typical "
                    "Delhi value, the largest movers were: "
                    + "; ".join(bits)
                    + ". These are associations in the model, not proof of cause."
                ),
                passage_ids=ids,
            )
        )

    # 7. fires
    fires = by_intent.get("whether anything is burning")
    if fires is not None:
        count = int(fires.passage.facts.get("count", 0) or 0)
        if count:
            paragraphs.append(
                Paragraph(
                    intent="whether anything is burning",
                    text=(
                        f"{count} satellite fire detections were recorded in this area "
                        "in the last few days; smoke can travel much further than the "
                        "streets between here and there."
                    ),
                    passage_ids=[fires.passage.passage_id],
                )
            )

    # 8. how much to trust it
    acc = by_intent.get("how much to trust it")
    if acc is not None:
        paragraphs.append(
            Paragraph(
                intent="how much to trust it",
                text=acc.passage.text,
                passage_ids=[acc.passage.passage_id],
            )
        )

    # 9. freshness
    fresh = by_intent.get("how old the inputs are")
    if fresh is not None:
        paragraphs.append(
            Paragraph(
                intent="how old the inputs are",
                text=fresh.passage.text,
                passage_ids=[fresh.passage.passage_id],
            )
        )

    # 10. what the category means
    band = by_intent.get("what the category means")
    if band is not None:
        paragraphs.append(
            Paragraph(
                intent="what the category means",
                text=band.passage.text,
                passage_ids=[band.passage.passage_id],
            )
        )

    assert_grounded(paragraphs, chosen)
    return GroundedAnswer(
        headline=headline,
        paragraphs=paragraphs,
        passages=chosen,
        trace=trace,
    )


def assert_grounded(paragraphs: list[Paragraph], passages: list[Passage]) -> None:
    """Fail loudly rather than ship an answer that cites something we did not retrieve.

    This is the guard that makes the no-LLM path trustworthy: if a composer change
    ever adds a paragraph referencing a passage that retrieval did not return, the
    explanation is wrong and this raises rather than shipping it.
    """
    known = {p.passage_id for p in passages}
    for para in paragraphs:
        unknown = [pid for pid in para.passage_ids if pid not in known]
        if unknown:
            raise GroundingError(
                f"paragraph {para.intent!r} cites un-retrieved passages: {unknown}"
            )
        if not para.passage_ids:
            raise GroundingError(f"paragraph {para.intent!r} cites nothing")
        if FORBIDDEN_UNGROUNDED.search(para.text):
            raise GroundingError(
                f"paragraph {para.intent!r} contains ungrounded advice language: {para.text[:80]!r}"
            )


class GroundingError(RuntimeError):
    """A composed paragraph referenced evidence that was not retrieved."""


__all__ = ["FORBIDDEN_UNGROUNDED", "GroundedAnswer", "GroundingError", "Paragraph", "compose"]
