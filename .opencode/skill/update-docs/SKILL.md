---
name: update-docs
description: Update Dhuan Detective documentation and mermaid diagrams. Use when behaviour, architecture, model, agents, APIs or data sources change. Lists which document owns which diagram and how to build the site strictly.
---

# Update docs and diagrams

## Ownership

| Change | Update |
|---|---|
| Route added/removed | `openapi/openapi.yaml`, `docs/API.md` |
| Data flow, pipeline, sequence | `docs/ARCHITECTURE.md` (flowchart + sequence + state + ER) |
| Algorithm change | `docs/ALGORITHM.md` |
| Model change | `docs/MODEL.md` + regenerate `docs/MODEL_CARD.md` |
| Agent/tool change | `docs/AGENTS_DESIGN.md` |
| AWS service change | `docs/AWS.md` |
| New data source | `docs/DATA_SOURCES.md` + `docs/DATA_COLLECTION.md` |
| Decision | new `docs/adr/NNNN-*.md` |
| User-visible behaviour | `README.md` |
| Dependencies | `docs/TECHNOLOGY_STACK.md` |
| Engineering rules | `docs/RULES.md` |

## Diagram rules

- Every doc above carries at least one mermaid diagram (not images).
- Keep diagrams consistent with code — a wrong diagram is worse than none.

## Build strictly

```bash
make docs   # mkdocs build --strict: broken links fail the build
```

## Rule

If the change altered behaviour and no doc changed, the task is not done.
