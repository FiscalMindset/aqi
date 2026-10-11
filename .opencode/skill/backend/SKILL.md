---
name: backend
description: Backend engineering skill for Dhuan Detective. Use when adding or changing FastAPI routes, ingest clients, stores, pipeline handlers, or any Python module under backend/src/dhuan. Enforces the production-route checklist, http discipline, error typing, logging/metrics conventions, and the mypy --strict / ruff gates.
---

# Backend engineering skill

## When to use

Any change under `backend/src/dhuan/` — routes, ingest, geo, model, agents, stores, pipeline, alerts, core.

## Non-negotiables

1. No TODO/FIXME/`pass` bodies/`NotImplementedError`/commented-out code in `src`.
2. No fabricated values. Missing credentials raise `NotConfiguredError`; dead upstreams raise `UpstreamError`; the UI shows stale, not invented data.
3. Every store/upstream call has timeouts, retries with backoff + jitter, a log line with the correlation id, and a metric.
4. Errors are typed `Problem`s (RFC 9457) — never an unhandled 500.
5. `Decimal` for DynamoDB numbers (float raises `TypeError`).

## Route checklist (rule 2 — a route is not done without all of these)

- [ ] Pydantic request schema in `api/schemas.py`
- [ ] Typed response model in `api/models.py` with OpenAPI examples
- [ ] Query/Path validation via `Annotated[...]`
- [ ] Coverage guards raise `outside_coverage_problem` (422 problem+json)
- [ ] Store failures converted with `upstream_problem` (503 problem+json)
- [ ] Correlation-id logging on success and failure paths
- [ ] EMF metric on the served path (`record("EstimatesServed", 1)` style)
- [ ] Retry/timeout on every outbound call
- [ ] Unit tests (respx-mocked upstreams)
- [ ] Integration tests against containers
- [ ] Covered by the Schemathesis contract suite automatically

## Pattern to copy

`backend/src/dhuan/api/routers/estimate.py` — validation → coverage check → cached feeds with staleness → typed response. Cut and adapt; don't re-invent.

## Commands (run before every commit)

```bash
cd backend
uv run ruff check src tests
uv run mypy --strict src
uv run pytest tests/unit -q
uv run pytest tests/integration -q        # containers must be up
```

## Gotchas already learned here

- DynamoDB rejects floats → use `_dec()`.
- `asyncio.run` once per handler: create AND close the client inside one loop.
- Overpass mirrors reject generic User-Agents; regional mirrors (osm.ch) serve national extracts only.
- FastAPI binds `Depends(get_settings)` at decoration time; patch via `app.dependency_overrides` in tests, and call `reset_clients()` when settings change.
- The default boto3 session caches credentials process-wide; set `HOME` and reset `boto3.DEFAULT_SESSION` in test fixtures.
