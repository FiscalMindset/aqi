# infra/AGENTS.md

AWS infrastructure: SAM template, Step Functions ASL, configs, dashboards.

## Commands

```bash
sam validate --template infra/template.yaml --lint      # needs the SAM CLI
cfn-lint infra/template.yaml                             # zero findings today
python -c "import json; json.load(open('infra/state-machine.asl.json'))"
```

## Rules (short form)

1. Everything is infra-as-code: no console changes without updating the template.
2. Every state machine task has Retry (exponential backoff + jitter), Catch, and a failure path that records feed status + emits a metric.
3. Parameterise per environment; no account IDs or ARNs hardcoded.
4. Least-privilege IAM per function; no wildcard resources except where AWS requires (`bedrock:InvokeModel` scope).
5. Log retention, TTLs and the smallest resource sizes are deliberate — see `../docs/COST.md`.
6. `cfn-lint` must stay at zero findings before committing.
