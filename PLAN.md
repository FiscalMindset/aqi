# Dhuan Detective — Build Plan

> Living plan for building Dhuan Detective end to end. Phase gates follow the
> project brief (`AGENTS.md` section 10). This file is updated as decisions are
> refined; every major decision also gets an ADR under `docs/adr/`.

## North star

For any point in Delhi: estimate street-level PM2.5 hourly with a validated
model, identify likely upwind sources with geospatial search, explain causes
with an AI agent that shows its evidence, and give tailored advice — honestly,
with uncertainty and freshness always visible.

## Non-negotiable rules (summary of AGENTS.md §1)

1. No stubs, no placeholders, no fake production data in `src`. `DEMO_MODE`
   may serve recorded data but must show a permanent visible banner and
   defaults to off. CI greps `src` for forbidden tokens.
2. Every route: validation, typed response, RFC 9457 errors, timeouts,
   retries with backoff+jitter, structured logs with correlation id, metrics,
   tracing, throttling, authorization where relevant, OpenAPI entry with
   examples, unit + integration + contract tests.
3. Fail soft: last good value + `data_age_seconds` + visible stale state.
   Never invent values, never swallow exceptions silently.
4. Honesty: estimates carry 80% intervals; agent says "likely contributors"
   with evidence; model-card metrics come from the evaluation script only.
5. Verify external APIs against current docs; record in
   `docs/DATA_SOURCES.md`.
6. Run lint/typecheck/tests after every task; commit per completed task with
   Conventional Commits.
7. No secrets in repo; `.env.example` names only; gitleaks in pre-commit + CI.
8. No real AWS creds here: develop against Docker (OpenSearch, LocalStack),
   validate with `sam validate` + `cfn-lint`, and clearly mark verified-local
   vs needs-deploy.
9. Sensible defaults recorded as ADRs; do not ask questions unless blocked.
10. Plan first: `PLAN.md` + `TASKS.md` kept up to date.

## Verified environment facts (checked 2026-10-15, macOS arm64)

| Item | Result |
|---|---|
| Python | 3.12.13 (`/opt/homebrew/bin/python3.12`), managed via `uv` (0.11.7) |
| Node | 24.15.0, npm 11.12.1 |
| Docker | 29.4.0, daemon running, compose v5.1.2 |
| Open-Meteo | `api.open-meteo.com` reachable HTTP 200, no key required |
| OpenAQ API v3 | reachable, **requires `X-API-Key`** (401 without). Rate limit 60/min, 2000/hour |
| OpenAQ archive S3 | `https://openaq-data-archive.s3.amazonaws.com` public, no creds; per-location daily CSV.gz |
| Overpass | `overpass-api.de` busy/504 intermittently → use mirrors (`overpass.kumi.systems`, `overpass.private.coffee`) with retry |
| CPCB live API | `api.cpcbccr.com` unreachable from this network; OpenAQ mirrors CPCB stations anyway |
| GitHub | reachable; git 2.54.0 |

## Phase plan

### Phase 1 — Foundation
Repo layout, `AGENTS.md`, `PLAN.md`/`TASKS.md`, tooling (uv, ruff, mypy
strict, pytest), pre-commit, Docker compose (OpenSearch + LocalStack), CI
skeleton (green), MkDocs skeleton. **Gate:** `make help` works, CI skeleton
present, docs site builds.

### Phase 2 — Data and geo
Ingest clients (`openaq.py`, `weather.py`, `firms.py`, `osm.py`) with
timeouts/retries/freshness; OSM→OpenSearch seeding; H3 grid; geo math with
Hypothesis property tests; routes `/health`, `/ready`, `/v1/sources`,
`/v1/stations`, `/v1/status`. **Gate:** integration tests green against
containers.

### Phase 3 — Model
Features from real historical station data (OpenAQ archive snapshot) +
Open-Meteo historical weather + static geo features; HistGradientBoosting
quantile 80% interval; leave-one-station-out + temporal holdout; baseline
comparison; model card generated from real metrics; `/v1/estimate`,
`/v1/grid`, `/v1/validation`. **Gate:** model tests prove no leakage, coverage
within tolerance, `/v1/estimate` returns real numbers.

### Phase 4 — Agents
Strands attribution + advisory agents, typed tools, guardrails, eval suite;
`/v1/explain`. **Gate:** agent evals deterministic in CI.

### Phase 5 — Pipeline and alerts
Step Functions ASL, EventBridge, SNS, subscriptions routes, DLQ + alarms.
**Gate:** pipeline handlers tested with LocalStack.

### Phase 6 — Frontend
Explorer (mobile-first, 3 breakpoints, i18n, a11y, PWA), deep links,
`/routes`, `/subscribe`, `/how-it-works`, `/methodology`, `/status`.
**Gate:** Playwright matrix + axe + Lighthouse budgets.

### Phase 7 — Hardening
Contract tests (Schemathesis), k6 load, security scans, coverage thresholds,
full e2e matrix. **Gate:** every layer green.

### Phase 8 — Delivery
SAM final + `sam validate`/cfn-lint/checkov, CD with OIDC, observability as
code, full docs, DEMO.md, BLOG.md, teardown script, final report.

## Commit policy (per user instruction)

Commit after **every** meaningful step (scaffold, module, test suite, doc),
not just at phase gates. Conventional Commits. History must tell the whole
story from empty dir to final state.
