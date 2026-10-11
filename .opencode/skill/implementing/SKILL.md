---
name: implementing
description: Implementation workflow skill for Dhuan Detective. Use when starting any new feature, task or phase. Enforces the plan-first workflow, task tracking in TASKS.md, the definition of done, commit granularity (every meaningful step, Conventional Commits), and the verification gate before each commit.
---

# Implementation workflow skill

## Order of work

1. **Plan** — update `PLAN.md` if the phase goals changed.
2. **Tasks** — add the items to `TASKS.md` before starting.
3. **Implement** — smallest reviewable increments.
4. **Verify** — lint, types, tests for the touched layers.
5. **Commit** — Conventional Commits, after **every** meaningful step, so the history tells the whole story from empty repo to final state.
6. **Update TASKS.md** — mark `[x]` only when the gate passed.

## Definition of done (brief §11)

- [ ] Code is real: no stubs, no placeholders, no fabricated data in `src`.
- [ ] New route satisfies the full rule-2 checklist (see backend skill).
- [ ] Tests exist at every relevant layer and pass.
- [ ] Lint + types clean.
- [ ] Docs and diagrams updated when behaviour changed (docs, README, skills).
- [ ] Committed with a Conventional Commit message.
- [ ] `DEMO_MODE` behaviour verified (banner visible, defaults off) if user-facing data changed.

## Commit rules

- `feat(scope)`, `fix(scope)`, `test(scope)`, `docs(scope)`, `chore(scope)`.
- Body: what changed and **why**, plus the evidence (commands/tests run).
- Never commit secrets; `.env.example` names only.

## Verification gate

```bash
# backend
cd backend && uv run ruff check src tests && uv run mypy --strict src && uv run pytest tests/unit -q
# frontend
cd frontend && npx tsc --noEmit && npm run lint && npm run test:unit
# docs (when touched)
make docs
```

If a command was not run, say so — never claim green.
