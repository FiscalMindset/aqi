# TODO — live work list

Single source of truth for what is in flight. Structural history lives in `TASKS.md`; this file is the always-current queue.

## In progress

- [ ] Push repositories: set two remotes — private `FiscalMindset/dhuan`, public `FiscalMindset/aqi` — and push `main` to both.

## Backlog (remaining phase-8 items)

- [ ] CI workflows: `ci.yml`, `cd.yml`, `model-train.yml`, `docs.yml`, `codeql.yml` (jobs: lint, types, forbidden tokens, unit, integration, contract, model, agent evals, frontend, e2e matrix, axe, Lighthouse, IaC validation, security scans, docker build+scan, OpenAPI drift, docs strict)
- [ ] `.pre-commit-config.yaml` + gitleaks hook
- [ ] `dependabot.yml`, `CODEOWNERS`, `pull_request_template.md`, `ISSUE_TEMPLATE/`
- [ ] `docs/DEPLOYMENT.md`, `docs/TESTING.md`, `docs/RUNBOOK.md`, `docs/SECURITY.md`, `docs/COST.md`, `docs/CONTRIBUTING.md`, `docs/DEMO.md`, `docs/BLOG.md`, `docs/CONTRIBUTING.md`
- [ ] `docs/API.md` generated from `openapi/openapi.yaml` (+ Swagger UI embed)
- [ ] `docs/adr/NNNN-*.md` — one ADR per major decision (coverage threshold, serve rule, agent backends, H3 res 8, conformal interval, FastAPI 3.0 pin)
- [ ] `.opencode/agent/*.md` — reviewer, test-writer, docs-writer, security-auditor, infra-engineer
- [ ] `.opencode/command/verify.md` + `release.md`
- [ ] `scripts/smoke.py`, `scripts/teardown.sh`, `scripts/backfill.py`, `load/k6` scripts
- [ ] `infra/dashboards/` CloudWatch dashboard as code
- [ ] `CHANGELOG.md` release flow

## Done (recent)

- [x] Live stack running: API on 127.0.0.1:8080 (demo mode), web on 127.0.0.1:4173
- [x] Real bugs fixed from the live run: estimate-tool `Depends` leak, evidence raw-result drop, CORS demo-banner header, map init error state
- [x] Docs: README, ARCHITECTURE, AWS, ALGORITHM, MODEL, BACKEND, FRONTEND, GRADIENT_BOOSTING, DATA_COLLECTION, RULES, TECHNOLOGY_STACK, AGENTS_DESIGN, MODEL_CARD
- [x] Skills: backend, frontend, ml, implementing, api-route, data-source, agent-tool, write-tests, update-docs, retrain-model, incident-response
