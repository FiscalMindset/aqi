# Engineering rules

Non-negotiable. Violating these is a failure even if tests pass. CI enforces the mechanical ones.

## 1. No stubs, no placeholders, no fake production data

- Forbidden in `src`: `TODO`, `FIXME`, `XXX`, `pass` as a body, `NotImplementedError`, `lorem ipsum`, hardcoded sample AQI values, commented-out code.
- Fixtures and recorded data live only under `tests/` or `fixtures/`.
- `DEMO_MODE=1` may serve recorded data, but the UI must show a **permanent, visible "Demo data" banner** whenever it is on, and it defaults to off.
- The CI job `forbidden-tokens` greps `src` and fails the build.

## 2. Every route is production-ready

Each API route delivers: request validation, typed response model, RFC 9457 `application/problem+json` errors, timeouts on every outbound call, retries with exponential backoff and jitter, structured logs with a correlation id, metrics, tracing, throttling, authorization where relevant, an OpenAPI entry with examples, unit tests, integration tests, and a contract test. A route missing any of these is not done.

## 3. Fail soft, never fail silent

- Upstream down → serve the last good value with an explicit `data_age_seconds` and a visible stale state.
- Never invent a value. Never swallow an exception without logging and a metric.

## 4. Honesty in output

- Estimates carry uncertainty intervals.
- The agent says "likely contributors" and cites evidence.
- Model-card metrics come from the evaluation script only. Never state or commit performance numbers you did not compute by running code.

## 5. Verify, don't assume

Read current official docs before using any API/SDK/service. Record findings in `docs/DATA_SOURCES.md`. If memory conflicts with the docs, the docs win. (This rule caught the Open-Meteo archive hostname, the Overpass contact-UA requirement, and the regional-mirror trap.)

## 6. Run what you write

After every task: lint, type-check and the relevant tests. Commit after each completed task with Conventional Commits. No commit for incomplete work.

## 7. No secrets in the repo

`.env.example` holds names only. Runtime secrets come from SSM Parameter Store or Secrets Manager. gitleaks runs in pre-commit and CI.

## 8. No fabricated deployments

Without real AWS credentials, develop against Docker (OpenSearch + LocalStack), validate with `sam validate` and `cfn-lint`, and clearly mark what was verified locally versus what needs a real deploy.

## 9. Sensible defaults, recorded

Every major decision gets an ADR in `docs/adr/`. Do not block on questions that a documented default can answer.

## 10. Plan first

`PLAN.md` and `TASKS.md` are maintained before and during work. Commit granularity is fine-grained so the full history tells the story.

## Enforcement map

| Rule | Enforced by |
|---|---|
| 1 | CI `forbidden-tokens` job + review |
| 2 | Schemathesis contract tests + route checklists in `.opencode/skill/add-api-route/` |
| 3 | Stale-path unit tests (`test_core.py::test_ttl_cache_serves_last_good_on_failure`) |
| 4 | `metrics.json` provenance hash + model-card generation |
| 5 | `docs/DATA_SOURCES.md` with verified dates |
| 6 | pre-commit + CI jobs (lint, types, tests) |
| 7 | gitleaks in pre-commit and CI |
| 8 | `DEPLOYMENT.md` verification matrix |
| 9 | `docs/adr/` directory |
| 10 | `PLAN.md`, `TASKS.md` |
