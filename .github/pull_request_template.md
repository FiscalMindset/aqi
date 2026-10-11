## What and why

<!-- one paragraph: the problem, the fix, the evidence -->

## Checklist (brief §2 + §11)

- [ ] No forbidden tokens in `src` (no TODO/pass bodies/placeholders)
- [ ] New route satisfies the full production checklist (validation, typed response, RFC 9457, timeouts, retries, correlation-id logs, metrics, OpenAPI entry, unit + integration + contract tests)
- [ ] `ruff`, `mypy --strict`, `eslint`, `tsc` clean where touched
- [ ] Tests pass for the touched layers (state which)
- [ ] Docs/diagrams updated (or a note why not needed)
- [ ] No secrets; `.env.example` only holds names
- [ ] Commits use Conventional Commits

## Evidence

```
# paste the commands you ran and their results
```
