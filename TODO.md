# TODO — live work list

Single source of truth for what is in flight. Structural history lives in `TASKS.md`; this file is the always-current queue.

## In progress

- [ ] `aws login` (human) → `sam build --use-container` → staging deploy →
      `scripts/smoke.py --env staging` (see docs/AWS_JOURNEY.md runbook)

## Remaining backlog

- [ ] `infra/dashboards/` CloudWatch dashboard as code (alarms exist in the template)
- [ ] Live agent evals gated behind `DHUAN_LIVE_AGENTS=1` (code path exists)
- [ ] `docs/API.md` Swagger-UI embedding (the page documents routes + examples; the
      interactive embed needs the published site URL)

## Done (recent)

- [x] **aws_journey.md** — the real credential story (login refresh `expiresIn`,
      HOME isolation, `boto3.DEFAULT_SESSION` reset), cfn-lint findings fixed,
      and the deployment runbook for when credentials exist
- [x] **Live stack verified end to end**: API on 127.0.0.1:8080, web on
      127.0.0.1:4173 — estimate, stations, sources, /v1/explain with real
      landfill causes, agent trace, Hindi switch, map canvas painting
- [x] Real bugs fixed from the live run: estimate-tool `Depends` leak, evidence
      raw-result drop, CORS demo-banner header, map loading/error states,
      useful outside-coverage error text
- [x] Git history rewritten so **every commit is authored by FiscalMindset**
      (vicky kumar <254638087+FiscalMindset@users.noreply.github.com>) and
      force-pushed to both remotes
- [x] CI (14 jobs), CD with OIDC + canary, model-train, docs, CodeQL
      workflows; dependabot, CODEOWNERS, PR/issue templates, pre-commit + gitleaks
- [x] Docs: README, ARCHITECTURE, AWS, ALGORITHM, MODEL, BACKEND, FRONTEND,
      GRADIENT_BOOSTING, DATA_COLLECTION, RULES, TECHNOLOGY_STACK,
      AGENTS_DESIGN, MODEL_CARD, TESTING, DEPLOYMENT, RUNBOOK, SECURITY, COST,
      CONTRIBUTING, DEMO, BLOG, API, DATA_SOURCES, 8 ADRs
- [x] Skills: backend, frontend, ml, implementing, api-route, data-source,
      agent-tool, write-tests, update-docs, retrain-model, incident-response
- [x] Subagents: reviewer, test-writer, docs-writer, security-auditor,
      infra-engineer; commands: /verify, /release
- [x] openapi/openapi.yaml committed (12 routes, 3.0.3); scripts/smoke.py,
      scripts/teardown.sh, scripts/backfill.py, load/estimate.js, CHANGELOG.md
- [x] AGENTS.md at root + backend + frontend + infra (git identity documented)
- [x] MkDocs strict build green (33 pages)
