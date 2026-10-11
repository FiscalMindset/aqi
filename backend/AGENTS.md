# backend/AGENTS.md

FastAPI + model + agents + pipeline (Python 3.12, uv, mypy --strict).

## Commands

```bash
uv sync --extra dev
uv run uvicorn dhuan.api.app:app --reload            # :8000
uv run ruff check src tests
uv run ruff format src tests
uv run mypy --strict src
uv run pytest tests/unit -q                          # hermetic
uv run pytest tests/integration -q                   # needs docker compose test stack
uv run pytest tests/model tests/agent_evals -q
uv run pytest tests/contract -q
uv run pytest tests/unit tests/integration --cov=src/dhuan   # 84.65% today
```

## Rules (short form)

1. `src/` contains no stubs/TODOs/placeholders and no fabricated values.
2. Every route satisfies the production checklist in `../docs/RULES.md` §2.
3. All outbound calls go through `core/http.py` (timeouts, backoff+jitter, metrics).
4. Errors are typed `Problem`s (RFC 9457); a 503 problem is fine, a 500 is a bug.
5. DynamoDB numbers use `Decimal`.
6. Tests: unit (respx) + integration (containers) + contract (Schemathesis) + model + agent evals.
7. Model metrics come only from `model/evaluate.py`; regenerate `docs/MODEL_CARD.md`, never hand-edit.

See `../docs/BACKEND.md`, `../docs/ALGORITHM.md`, `../docs/MODEL.md` and the `.opencode/skill/backend` skill.
