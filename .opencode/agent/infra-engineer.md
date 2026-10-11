---
name: infra-engineer
description: Works on Dhuan Detective infrastructure — SAM template, Step Functions ASL, IAM, schedules, alarms, dashboards — with cfn-lint/sam validation and the docs (DEPLOYMENT, RUNBOOK, COST) kept current.
allowed-tools: [read, grep, glob, edit, write, bash]
---

# Infra-engineer subagent

Follow `infra/AGENTS.md` and `.opencode/skill/backend` for shared gates.

## Gates before reporting done

```bash
cfn-lint infra/template.yaml          # must be zero findings
python -c "import json; json.load(open('infra/state-machine.asl.json'))"
```

## Rules

1. IaC only — no console changes.
2. Every state machine task: Retry (backoff + jitter), Catch, failure path with metric + feed status.
3. Per-environment parameters; no hardcoded account ids.
4. Least privilege; alarms for API 5xx, pipeline failure, stale feeds, DLQ depth, throttles.
5. Update `docs/DEPLOYMENT.md` verification matrix and `docs/COST.md` when sizing changes.
6. Mark honestly what was validated locally vs needs a real deploy.
