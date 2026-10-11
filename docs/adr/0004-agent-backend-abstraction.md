# ADR 0004: Backend-agnostic agent runtime with a scripted fallback

## Status
Accepted

## Context
CI and demo mode must be deterministic and offline, while production must use Amazon Bedrock through the Strands Agents SDK. The brief requires a deterministic fake model in unit tests and live evals behind an env var.

## Decision
The agent loop is backend-agnostic: `BedrockBackend` (boto3 Converse with tool specs) and `ScriptedBackend` (replays a competent tool plan and synthesizes with identical evidence rules) implement the same interface. The evidence ids, guardrails, sanitisation and synthesis are shared, so what is tested is what ships.

## Alternatives considered
- Strands-only: cannot be tested deterministically without live Bedrock.
- Self-only: would duplicate production semantics in tests.

## Consequences
- CI runs every agent scenario offline in < 3 s.
- Live evals gated behind `DHUAN_LIVE_AGENTS=1`.
- One place to fix guardrail bugs (both backends share them).
