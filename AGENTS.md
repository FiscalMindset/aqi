# AGENTS.md — Dhuan Detective

Root instructions for AI agents working in this repository.

## Identity (git)

**Every commit must be authored by FiscalMindset.** Local config is already set:

```
user.name  = vicky kumar
user.email = 254638087+FiscalMindset@users.noreply.github.com
```

Do not invent commit identities. If you create a new clone, re-set both values from this file before the first commit.

## Remotes

- public:  `https://github.com/FiscalMindset/aqi.git`  (remote `pub`)
- private: `https://github.com/FiscalMindset/dhuan.git` (remote `priv`)

Push both after every commit batch:

```bash
git push pub main && git push priv main
```

## Project overview

Dhuan Detective: street-level PM2.5 estimation, upwind source attribution and persona advice for Delhi-NCR. Backend FastAPI + model + agents; frontend React PWA; infra SAM + Step Functions; docs MkDocs Material.

## Directory map

| Path | What lives there |
|---|---|
| `backend/src/dhuan/api/` | FastAPI app, routers, errors, middleware, deps |
| `backend/src/dhuan/agents/` | Strands-style attribution runtime, tools, guardrails |
| `backend/src/dhuan/model/` | features, train, evaluate, predict, CPCB categories |
| `backend/src/dhuan/geo/` | H3 grid, boundary, bearing/cone math, scoring |
| `backend/src/dhuan/ingest/` | openaq, weather, firms, osm clients |
| `backend/src/dhuan/store/` | dynamodb, opensearch, s3 access layers |
| `backend/src/dhuan/pipeline/` | Step Functions task handlers |
| `backend/src/dhuan/alerts/` | alert rules, hysteresis, SNS |
| `frontend/src/` | React app (explorer, routes, subscribe, status, methodology, how-it-works) |
| `infra/` | SAM template, state machine, samconfig |
| `docs/` | MkDocs site, ADRs, model card |
| `.opencode/` | skills, subagents, commands |
| `scripts/`, `fixtures/`, `load/` | seeding/smoke/teardown, recorded data, k6 |

## Commands

```bash
make dev            # docker: OpenSearch + LocalStack + backend + frontend
make test           # all backend layers
make lint           # ruff + eslint
make types          # mypy --strict + tsc
make docs           # mkdocs build --strict
make train          # reproducible model training
```

Per-area commands are documented in `docs/TECHNOLOGY_STACK.md`, `docs/BACKEND.md`, `docs/FRONTEND.md`.

## Non-negotiable rules (short form — full text in `docs/RULES.md`)

1. No stubs, no placeholders, no fake production data in `src`. Demo data only via `DEMO_MODE` with a permanent banner.
2. Every route: validation, typed response, RFC 9457 errors, timeouts, retries, correlation-id logs, metrics, tracing, throttling, OpenAPI, unit + integration + contract tests.
3. Fail soft, never invent values.
4. Honest estimates with intervals; model metrics only from the evaluation script.
5. Verify external APIs against current docs; record in `docs/DATA_SOURCES.md`.
6. Run lint/types/tests after every task; commit with Conventional Commits after every meaningful step.
7. No secrets in the repo; `.env.example` names only.
8. No fabricated deploys; mark verified-local vs needs-deploy.
9. Record decisions as ADRs.
10. Keep `PLAN.md`, `TASKS.md`, `TODO.md` current.

## Definition of done

Tests at the touched layers pass; lint and types clean; docs/diagrams updated; committed with a Conventional Commit message; no forbidden tokens; demo behaviour verified if user-visible.

## Never

- Never claim a test/command passed without running it.
- Never commit secrets or a filled `.env`.
- Never commit metrics by hand — regenerate `docs/MODEL_CARD.md` from `metrics.json`.
- Never push to `main` with red CI.
