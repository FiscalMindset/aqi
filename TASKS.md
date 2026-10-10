# Dhuan Detective — Live Task Checklist

> Update after every task. Mark `[x]` only when lint, types and tests pass.
> Format: `- [x] task — evidence (command/run)` 

## Phase 1 — Foundation

- [x] Verify environment tooling (python/node/docker/network) — PLAN.md table
- [x] `git init` + Conventional Commits policy (user: commit every step)
- [x] `PLAN.md` written
- [x] `TASKS.md` written
- [ ] Root files: `.gitignore`, `.editorconfig`, `.env.example`, `LICENSE`
- [ ] `Makefile` (help/dev/test/lint/train/deploy/docs)
- [ ] `backend/pyproject.toml` + uv lock; `uv sync` works
- [ ] `AGENTS.md` (root) + `backend/AGENTS.md`
- [ ] `.pre-commit-config.yaml` (gitleaks, ruff, etc.)
- [ ] `docker/docker-compose.yml` (OpenSearch + LocalStack) with healthchecks
- [ ] `.github/workflows/ci.yml` skeleton
- [ ] `docs/` MkDocs Material skeleton + `mkdocs.yml`
- [ ] Phase 1 gate: `make help` + `mkdocs build --strict` + CI skeleton

## Phase 2 — Data and geo

- [ ] `core/` config, logging, metrics, tracing, http client, cache
- [ ] `ingest/openaq.py` + tests
- [ ] `ingest/weather.py` (Open-Meteo) + tests
- [ ] `ingest/firms.py` (NASA FIRMS) + tests
- [ ] `ingest/osm.py` (Overpass, mirrors) + tests
- [ ] `geo/` h3 grid, bearing/upwind math, scoring + Hypothesis tests
- [ ] `store/` dynamodb, opensearch, s3 clients (LocalStack-backed tests)
- [ ] `api/` FastAPI app shell: errors (RFC 9457), middleware, deps
- [ ] `GET /health`, `GET /ready`
- [ ] `GET /v1/sources` (+ OpenSearch seeding script)
- [ ] `GET /v1/stations`
- [ ] `GET /v1/status`
- [ ] Phase 2 gate: integration tests green

## Phase 3 — Model

- [ ] Fetch + snapshot real training data (OpenAQ archive + Open-Meteo)
- [ ] `model/features.py`, `train.py`, `evaluate.py`, `predict.py`
- [ ] Leave-one-station-out + temporal holdout; LOSO baseline comparison
- [ ] Leakage tests; coverage tests; regression baseline
- [ ] `docs/MODEL_CARD.md` generated from metrics
- [ ] `GET /v1/estimate`, `GET /v1/grid`, `GET /v1/validation`
- [ ] Phase 3 gate: model tests pass, honest model card

## Phase 4 — Agents

- [ ] `agents/tools` (5 typed tools) + guardrails
- [ ] Attribution agent + advisory agent (Strands, Bedrock model id from env)
- [ ] `POST /v1/explain`
- [ ] `tests/agent_evals/` fixture suite (6 scenarios incl. injection)
- [ ] Phase 4 gate: agent evals green

## Phase 5 — Pipeline and alerts

- [ ] `pipeline/` task handlers; `state-machine.asl.json`
- [ ] EventBridge hourly + monthly schedules (infra)
- [ ] `alerts/` rules, hysteresis, dedupe, SNS publisher
- [ ] `POST/DELETE /v1/subscriptions`
- [ ] DLQ + alarms (infra)
- [ ] Phase 5 gate: pipeline tests with LocalStack green

## Phase 6 — Frontend

- [ ] Vite + React + TS + Tailwind + MapLibre scaffold, PWA shell
- [ ] Explorer (search, map, panel, bottom sheet / side panel)
- [ ] Deep links `/place/:lat/:lon`
- [ ] `/routes`, `/subscribe` (+ confirmation flow)
- [ ] `/how-it-works` interactive, `/methodology`, `/status`
- [ ] i18n EN+HI, a11y WCAG 2.2 AA, dark/light, colorblind palette
- [ ] Phase 6 gate: Playwright matrix + axe + Lighthouse budgets

## Phase 7 — Hardening

- [ ] Schemathesis contract tests (zero 5xx)
- [ ] k6 smoke/load with thresholds
- [ ] Security: bandit, pip-audit, npm audit, Trivy, gitleaks, CodeQL
- [ ] Coverage thresholds (backend ≥85%, frontend ≥80%)
- [ ] Full e2e matrix (Chromium/Firefox/WebKit × 360/768/1280)
- [ ] `sam validate`, cfn-lint, checkov — zero high
- [ ] Phase 7 gate: all layers green

## Phase 8 — Delivery

- [ ] SAM template finalized; policies; dashboards as code
- [ ] CD: OIDC, staging/prod, canary + rollback, smoke.py
- [ ] Docs: ARCHITECTURE/API/MODEL_CARD/DATA_SOURCES/AGENTS_DESIGN/TESTING/
      DEPLOYMENT/RUNBOOK/SECURITY/COST/CONTRIBUTING/DEMO/BLOG + ADRs
- [ ] `.opencode/` agent skills, subagents, commands (`/verify`, `/release`)
- [ ] `scripts/teardown.sh`, `load/k6`
- [ ] Final report (built / verified vs unverified / limitations / next steps)
