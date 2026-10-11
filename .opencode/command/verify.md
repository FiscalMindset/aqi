---
name: verify
description: Run the full local verification gate (lint, types, all test layers, strict docs build) and report a results table. Use before every commit and to gate a PR.
---

# /verify — full local gate

Run each gate, capture the result, then print one table. Never claim a gate that was not run.

```bash
# backend
cd backend
uv run ruff check src tests                     # lint
uv run mypy --strict src                        # types
uv run pytest tests/unit -q                     # hermetic
uv run pytest tests/model tests/agent_evals -q  # model + agents (needs make train for model)
uv run pytest tests/contract -q                 # OpenAPI contract

# integration (only if the containers are up)
docker compose -f ../docker/docker-compose.test.yml up -d --wait
uv run pytest tests/integration -q
uv run pytest tests/unit tests/integration tests/agent_evals tests/model --cov=src/dhuan  # coverage

# frontend
cd ../frontend
npx tsc --noEmit && npm run lint && npm run test:unit
npx playwright test   # when browsers are installed

# docs + infra
make docs             # strict: broken links fail
cfn-lint infra/template.yaml
```

## Report format

| Gate | Command | Result |
|---|---|---|
| lint | `ruff check src tests` | … |
| types | `mypy --strict src` | … |
| unit tests | `pytest tests/unit` | … |
| integration | `pytest tests/integration` | … |
| contract | `pytest tests/contract` | … |
| model | `pytest tests/model` | … |
| agent evals | `pytest tests/agent_evals` | … |
| coverage | `--cov=src/dhuan` | …% |
| frontend unit | `npm run test:unit` | … |
| e2e | `npx playwright test` | … |
| docs | `mkdocs build --strict` | … |
| IaC | `cfn-lint` | … |

Verdict: **GREEN** only when every run row passed.
