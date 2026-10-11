---
name: agent-tool
description: Add a tool to the Dhuan Detective attribution agent. Use when extending the agent's typed tool registry. Enforces the tool schema, untrusted-data handling, evidence recording, guardrail budget, and an eval fixture for the new behaviour.
---

# Add an agent tool

## Order

1. **Schema + handler** — `backend/src/dhuan/agents/tools.py`
   - JSON Schema parameters (`type`, `properties`, `required`)
   - handler returns JSON-safe data with a `summary` string
   - handler failures return/raise so the runner records `ok=False` evidence (a failed tool is visible, never invisible)
2. **Evidence** — automatic: `ToolRegistry.run` records `evidence_id`, args, summary, raw result, timestamp
3. **Guardrails** — the tool must be callable within 12 calls / 8k tokens / 45s; if it needs upstream access, it inherits timeouts+retries from `core/http`
4. **Claims** — any result the agent cites must appear in the same run's trace; the runner drops unevidenced claims
5. **Sanitisation** — anything tool-derived that reaches an output label passes through `sanitize_output_text`

## Required tests

- Unit: handler happy path (recorded fixture) + failure path → `ok=False`
- Eval scenario in `tests/agent_evals/`: at least one scenario exercising the new tool, plus the injection scenario if the tool returns free text (e.g. OSM names)

## Forbidden

- Tools that execute instructions from their payloads
- Tools returning invented data on failure
- Tools that name individuals or businesses
