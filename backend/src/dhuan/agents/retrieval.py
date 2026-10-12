"""Retrieval for the explanation layer.

This is the R half of the product's retrieval-augmented answer. The whole point
is that **the answer must be derivable without an LLM**: we retrieve a small set
of typed, citable passages about the point being asked about, and the narrative
in `dhuan.agents.narrative` is composed from exactly those passages. An LLM, when
one is available, is allowed to rewrite the composed text but is never allowed to
introduce a fact that is not in a passage.

Why this shape:

* Every passage carries provenance (where the number came from, how old it is,
  whether it is a measurement or a model output), so the composer can state it
  honestly and the UI can link to it.
* Retrieval is fielded rather than a flat vector search: we know which *kind* of
  fact answers which *part* of the question, and a keyword index over free text
  would blur exactly the distinctions that matter here (a measured 226 ug/m3 is
  not the same claim as a modelled 223).
* Scores are explicit and inspectable. `retrieval_trace` ships to the client so
  a reader can see why each passage was retrieved.

No embedding model, no vector store, no network: retrieval runs from data the
tools already returned, which is what makes the explanation path survive when
every external service is degraded.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

PassageKind = Literal[
    "station_reading",
    "station_trend",
    "model_estimate",
    "model_parameters",
    "model_accuracy",
    "source_upwind",
    "source_nearby",
    "wind",
    "ventilation",
    "fire_activity",
    "cpcb_band",
    "freshness",
    "coverage",
]

# Which question each kind of passage answers. Used to guarantee coverage of the
# explanation rather than hoping a scorer surfaces everything important.
INTENT_BY_KIND: dict[str, str] = {
    "station_reading": "what is being measured nearby",
    "station_trend": "is it getting better or worse",
    "model_estimate": "what we estimate here",
    "model_parameters": "what moved that estimate",
    "model_accuracy": "how much to trust it",
    "source_upwind": "what is upwind of here",
    "source_nearby": "what is close to here",
    "wind": "which way the air is moving",
    "ventilation": "whether the air can clear",
    "fire_activity": "whether anything is burning",
    "cpcb_band": "what the category means",
    "freshness": "how old the inputs are",
    "coverage": "where our data is thin",
}

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "of", "at", "by",
    "for", "with", "about", "this", "that", "it", "its", "and", "or", "to",
    "in", "on", "from", "as", "we", "our", "you", "your", "here", "there",
})


@dataclass(slots=True)
class Passage:
    """One citable fact."""

    passage_id: str
    kind: PassageKind
    text: str
    facts: dict[str, Any] = field(default_factory=dict)
    #: higher = more trustworthy for making a claim
    authority: float = 0.5
    #: true when the passage reports an observation rather than a model output
    measured: bool = False
    #: ISO timestamp of the underlying observation, if any
    observed_at: str | None = None
    #: seconds old at retrieval time
    age_seconds: float | None = None
    #: link a reader can verify
    source_url: str | None = None
    #: what produced it, for the trace
    evidence_id: str | None = None

    def age_phrase(self) -> str:
        if self.age_seconds is None:
            return ""
        hours = self.age_seconds / 3600.0
        if hours < 1:
            return "under an hour ago"
        if hours < 48:
            return f"{hours:.0f} h ago"
        days = hours / 24.0
        if days < 60:
            return f"{days:.0f} days ago"
        months = days / 30.44
        if months < 24:
            return f"{months:.0f} months ago"
        return f"over {months / 12:.0f} years ago"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passage_id": self.passage_id,
            "kind": self.kind,
            "text": self.text,
            "facts": self.facts,
            "authority": round(self.authority, 3),
            "measured": self.measured,
            "observed_at": self.observed_at,
            "age_seconds": self.age_seconds,
            "age_phrase": self.age_phrase(),
            "source_url": self.source_url,
            "evidence_id": self.evidence_id,
            "intent": INTENT_BY_KIND.get(self.kind, ""),
        }


@dataclass(slots=True)
class ScoredPassage:
    passage: Passage
    score: float
    reasons: list[str]


def _terms(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in _STOPWORDS and len(t) > 1
    ]


def _bm25(
    query_terms: list[str],
    passages: list[Passage],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> dict[str, float]:
    """Plain BM25 over the passage texts. Small corpus, so this is enough and
    it stays inspectable."""
    if not query_terms or not passages:
        return {}
    docs = [_terms(p.text) for p in passages]
    lengths = [len(d) for d in docs]
    avg_len = (sum(lengths) / len(lengths)) if lengths else 1.0
    n = len(docs)
    df: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    scores: dict[str, float] = {}
    for i, doc in enumerate(docs):
        counts: dict[str, int] = {}
        for term in doc:
            counts[term] = counts.get(term, 0) + 1
        score = 0.0
        for term in query_terms:
            f = counts.get(term, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            denom = f + k1 * (1 - b + b * lengths[i] / avg_len)
            score += idf * (f * (k1 + 1)) / denom
        scores[passages[i].passage_id] = score
    return scores


def retrieve(
    passages: Iterable[Passage],
    query: str,
    *,
    top_k: int = 12,
    max_age_seconds: float | None = None,
) -> list[ScoredPassage]:
    """Rank passages for a question.

    Scoring combines lexical relevance (BM25), authority (a measured reading
    outranks a model output when both match), and a staleness penalty. Ties break
    on passage id so retrieval is deterministic.
    """
    items = list(passages)
    if not items:
        return []
    lexical = _bm25(_terms(query), items)
    max_lex = max(lexical.values(), default=0.0) or 1.0
    scored: list[ScoredPassage] = []
    for p in items:
        if (
            max_age_seconds is not None
            and p.age_seconds is not None
            and p.age_seconds > max_age_seconds
        ):
            continue
        reasons: list[str] = []
        lex = lexical.get(p.passage_id, 0.0)
        score = 0.0
        if lex > 0:
            normalised = lex / max_lex
            score += 0.65 * normalised
            reasons.append(f"matches the question ({normalised:.2f})")
        else:
            score += 0.05  # keep everything reachable as a weak candidate
        score += 0.25 * p.authority
        if p.authority >= 0.9:
            reasons.append("authoritative (measured)")
        elif p.authority < 0.4:
            reasons.append("weak evidence")
        if p.measured:
            score += 0.05
        if p.age_seconds is not None:
            hours = p.age_seconds / 3600.0
            if hours > 72:
                penalty = min(0.25, 0.05 * math.log1p(hours / 72.0))
                score -= penalty
                reasons.append(f"stale ({self_age(p.age_seconds)})")
            elif hours <= 3:
                score += 0.05
                reasons.append("fresh")
        scored.append(ScoredPassage(passage=p, score=round(score, 5), reasons=reasons))
    scored.sort(key=lambda s: (-s.score, s.passage.passage_id))
    return scored[:top_k]


def self_age(seconds: float) -> str:
    """Readable age, shared with the email template so both say the same thing."""
    hours = seconds / 3600.0
    if hours < 1:
        return "under an hour"
    if hours < 48:
        return f"{hours:.0f} h"
    days = hours / 24.0
    if days < 60:
        return f"{days:.0f} days"
    months = days / 30.44
    if months < 24:
        return f"{months:.0f} months"
    return f"{months / 12:.0f} years"


def group_by_intent(scored: list[ScoredPassage]) -> dict[str, ScoredPassage]:
    """Best passage per question intent, so the composer cannot silently skip one."""
    best: dict[str, ScoredPassage] = {}
    for s in scored:
        intent = INTENT_BY_KIND.get(s.passage.kind, s.passage.kind)
        if intent not in best or s.score > best[intent].score:
            best[intent] = s
    return best


__all__ = [
    "INTENT_BY_KIND",
    "Passage",
    "PassageKind",
    "ScoredPassage",
    "group_by_intent",
    "retrieve",
    "self_age",
]
