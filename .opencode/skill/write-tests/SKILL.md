---
name: write-tests
description: Write tests for Dhuan Detective at the right layer. Use when adding any test. Covers where tests go, naming, fixtures vs recorded data, coverage thresholds, the container-backed integration suites, hypothesis property tests, contract tests, and agent evals.
---

# Write tests

## Layer map

| Layer | Location | Needs | Command |
|---|---|---|---|
| Unit | `backend/tests/unit` | nothing | `uv run pytest tests/unit -q` |
| Integration | `backend/tests/integration` | OpenSearch + LocalStack | `docker compose -f docker/docker-compose.test.yml up -d --wait` |
| Contract | `backend/tests/contract` | nothing | `uv run pytest tests/contract -q` |
| Model | `backend/tests/model` | `models/metrics.json` | `make train` first |
| Agent evals | `backend/tests/agent_evals` | nothing | `uv run pytest tests/agent_evals -q` |
| Frontend unit | `frontend/tests/unit` | nothing | `npm run test:unit` |
| E2E + a11y | `frontend/tests/e2e`, `tests/a11y` | preview build | `npx playwright test` |

## Rules

- Recorded data lives in `tests/fixtures/` **with** a provenance block (source, fetch date, licence).
- Pin the request shape (URL, params, headers) in every upstream-mocking test.
- Fixtures never live in `src/`.
- Integration tests: use the `env`/`dynamodb`/`s3`/`source_index` conftest fixtures; they isolate `HOME` and reset the boto3 default session.
- Geo math → Hypothesis property tests (bearing, cone, wrap-around).
- Any route change must keep the Schemathesis suite green (no unhandled 5xx).

## Coverage

- Backend: 84.65% measured; `fail_under = 84` with the rationale documented in `backend/pyproject.toml`.
- Frontend: 87% lines; thresholds `lines 80, functions 70, branches 65` in `vite.config.ts` (React render props resist higher function coverage in jsdom).
