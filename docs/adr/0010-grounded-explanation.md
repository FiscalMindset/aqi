# 0010 - Grounded explanation without an LLM, optional Groq fluency pass

- Status: accepted
- Date: 2026-10-12

## Context

The product's third promise is "explain". A user standing on a street wants to
know *why* the air is bad, not what a model computed. That is naturally an LLM
task, which introduced three problems:

1. Bedrock model access is account-gated and was unavailable here, so the
   product's headline feature could not run at all.
2. An LLM asked to explain numbers will occasionally invent one. On a page whose
   whole value is that the numbers are trustworthy, that is unacceptable.
3. An explanation with no LLM is needed anyway for latency and cost.

## Decision

Split the explanation into two layers, and make the LLM the optional one.

**Layer 1 - grounded composition (always runs, no LLM).**

1. `corpus.py` turns the tool evidence into typed `Passage` objects. Every
   passage is a fact that can be pointed at, carrying provenance, an authority
   weight, a freshness measure and, where possible, a source link.
2. `retrieval.py` scores them with fielded BM25 plus authority and staleness
   weighting, then groups by intent so a question about upwind sources cannot be
   answered with a downwind one.
3. `narrative.py` composes an answer **only** from passages retrieval actually
   returned. A missing passage produces no paragraph rather than a generic one.
   Attribution is allowed to come back empty.

`assert_grounded` raises `GroundingError` if a paragraph cites a passage that
was not retrieved, cites nothing, or contains advice language ("you should",
"we recommend") that no tool can support.

**Layer 2 - Groq fluency pass (optional).**

Groq receives the composed text and the passages it came from, and may only
reword. Its output is discarded unless it introduces **no numeric token that was
not already in the grounded text**. Every failure - no key, disabled, 4xx, 5xx,
429, connect error, timeout, HTML instead of JSON, no choices, null content,
refusal, rambling, an invented number - returns the composed text with
`served_by: composed-grounded`.

## Consequences

- The explanation works with every external service down. Verified: with
  `GROQ_API_KEY` removed the response is byte-identical to the composed text,
  same paragraphs, same citations.
- A hallucinated measurement cannot reach a user through the fluency layer,
  even though that layer is an LLM.
- The response reports `prose_served_by` separately from `served_by`, so which
  layer produced the structured attribution and which produced the prose is
  auditable rather than assumed.
- Known limit: a rewrite that adds advice *without* adding a number still passes
  the guard. That is why the composed text remains the audit trail and the
  paragraphs keep their citations regardless of any rewrite.
- `gpt-oss-120b` is a reasoning model and spends part of its token budget on
  reasoning before emitting prose. The default budget is 3000 with one retry
  that triples it when the response comes back empty with `finish_reason=length`.