# Changelog

All notable changes to Dhuan Detective. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Full product: H3-res-8 PM2.5 estimation with a conformal 80% interval, upwind
  source attribution from OpenStreetMap via OpenSearch, Strands/Bedrock
  attribution agent with visible evidence, persona advice, alerts with
  hysteresis, cleanest-route comparison, explorer/status/methodology PWA in
  English and Hindi.
- 230 backend tests (unit, integration, contract, model, agent evals) at
  84.65% coverage; 45 frontend unit tests; 80 Playwright tests across four
  browser projects with axe and responsive budgets.
- Documentation suite: README, ARCHITECTURE, AWS, ALGORITHM, MODEL, BACKEND,
  FRONTEND, GRADIENT_BOOSTING, DATA_COLLECTION, RULES, TECHNOLOGY_STACK,
  MODEL_CARD (generated), AGENTS_DESIGN, TESTING, DEPLOYMENT, RUNBOOK,
  SECURITY, COST, CONTRIBUTING, DEMO, BLOG, API + 8 ADRs.
- OpenCode integration: 11 skills, 5 subagents, `/verify` and `/release`.

### Verified
- cfn-lint zero findings; ASL valid; 230 tests green; Playwright matrix green;
  production-grade Lighthouse budgets wired in CI.
- Published to GitHub: public `FiscalMindset/aqi`, private `FiscalMindset/dhuan`.

### Not verified
- No real AWS deploy (no credentials in the build environment): `sam deploy`,
  staging smoke and production release are CI-gated and documented in
  `docs/DEPLOYMENT.md`.

## [0.1.0] - 2026-10-11

### Added
- Phase 1-8 build: backend (FastAPI, model, agents, pipeline, alerts), frontend
  (React PWA), infra (SAM + Step Functions), CI/CD with OIDC.

[Unreleased]: https://github.com/FiscalMindset/aqi/compare/v0.1.0...main
