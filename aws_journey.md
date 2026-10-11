# AWS journey

How Dhuan Detective's AWS work actually went — the order it happened, what broke, and what we learned. Written to be read by anyone picking the project up, and by the judges who ask "what did you actually do on AWS?"

## Phase 0 — Decisions before touching AWS

1. **Region `ap-south-1` (Mumbai)** — closest to Delhi-NCR users; Bedrock model availability checked for the region.
2. **Serverless everything** — a two-person team, hourly data pipeline, no servers to patch.
3. **One container image, several handlers** — the API and the Step Functions tasks share `backend/Dockerfile` (different `CMD` per handler).
4. **Model id from env** — `BEDROCK_MODEL_ID` never hardcoded, per the brief.
5. **Local-first** — the build machine had no AWS credentials, so the whole stack was developed against Docker (OpenSearch + LocalStack) first.

## Phase 1 — Local stack before AWS

Started with `docker/docker-compose.yml` (OpenSearch + LocalStack). What we hit:

| Issue | Symptom | Fix |
|---|---|---|
| OpenSearch memory lock | container exits immediately | `bootstrap.memory_lock` + `ulimits.memlock = -1` |
| Security plugin blocking writes | 401 on every request | `DISABLE_SECURITY_PLUGIN=true`, `DISABLE_INSTALL_DEMO_CONFIG=true` |
| LocalStack "unhealthy" | `docker compose --wait` times out after 4 minutes even though every service reports `available` | Health check only greps for `dynamodb`; the slow part is service boot. We learned to poll `/health` ourselves |
| Port 8000 already in use | `bind: address already in use`, API never starts | moved local API to 8080; CI must not assume 8000 |

## Phase 2 — Writing the infrastructure

`infra/template.yaml` + `infra/state-machine.asl.json` with cfn-lint as the gate. Findings cfn-lint caught (all fixed):

1. **`Runtime` on a container-image function** (E3685) — image functions cannot set `Runtime`; removed it from `Globals.Function`.
2. **`AWS_REGION` is a reserved Lambda env var** (E3663) — dropped it; boto3 resolves the region itself.
3. **`SSM_PARAMETER_PREFIX` in function env** (E1019/E3030) — the parameter resource was in the way; removed and used the literal path.
4. **`ComparisonOperatorGreaterThanThreshold: true`** (E3002) — not a CloudWatch property; the correct property is `ComparisonOperator: GreaterThanThreshold` plus `TreatMissingData: notBreaching`.
5. **Redundant `DependsOn`** (W3005) — cfn-lint proved the dependency was already implied by `Ref`/`GetAtt`.

Result: **cfn-lint 1.57.2 reports zero findings.** ASL JSON validated. `sam validate`/`sam build --use-container` not run locally (no SAM CLI in this environment) — documented as needs-deploy.

## Phase 3 — The credential wall (the real story)

This is the part that cost the most time, and it is the most useful thing in this document.

### What happened

The machine had a previous `aws login` SSO session. Every boto3 call in tests tried to refresh it and failed:

```
botocore.exceptions.LoginRefreshRequired:
  Your session has expired or credentials have changed. Please reauthenticate using 'aws login'.
KeyError: 'expiresIn'
```

The `KeyError: 'expiresIn'` is the confusing part: it comes from `botocore/credentials.py` trying to parse a login-token refresh response, so it looks like a code bug but is actually an environment problem.

### The five things that fixed it

1. **Isolate `HOME` in test fixtures** — `~/.aws` on the dev machine must not leak into tests. The conftest points `HOME` at a temp dir with empty `config`/`credentials` files.
2. **Reset `boto3.DEFAULT_SESSION = None`** — the default session caches resolved credentials **process-wide**; once the login provider is selected, it stays selected for the whole pytest run.
3. **Static dummy credentials in env** — `AWS_ACCESS_KEY_ID=test` + `AWS_SECRET_ACCESS_KEY=test` for LocalStack, so the provider chain stops at `env`.
4. **`AWS_CONFIG_FILE` / `AWS_SHARED_CREDENTIALS_FILE`** pointed at empty files, so no profile is discovered.
5. **For real deploys** — use the AWS CLI login the user runs (`aws login` / `aws configure`), or GitHub OIDC in CI (already wired in `cd.yml`, no long-lived keys).

### Rule we wrote down

Never let `~/.aws` state decide test outcomes. Tests own their credentials; production uses OIDC.

## Phase 4 — What is deployed vs not

| | |
|---|---|
| **Deployed for real** | nothing yet — no credentials in the build environment |
| **Verified locally** | cfn-lint zero findings, ASL valid, 230 backend tests, 80 Playwright tests, live API on :8080 and web on :4173 serving real data + real OSM sources |
| **Ready to deploy** | `sam build` → `sam deploy --config-env staging` via `cd.yml`, or by hand once `aws login` succeeds |

## Phase 5 — Deployment runbook (for when credentials exist)

```bash
# 1. authenticate (human does this; CI uses OIDC)
aws login          # or: aws configure

# 2. put secrets (never in the repo)
aws ssm put-parameter --name /dhuan/openaq-api-key --type SecureString --value "..."
aws ssm put-parameter --name /dhuan/firms-map-key --type SecureString --value "..."
aws ssm put-parameter --name /dhuan/prod/api-url --type String --value "https://..." 

# 3. build + deploy
sam build --template infra/template.yaml --use-container
sam deploy --config-file infra/samconfig.toml --config-env staging \
  --parameter-overrides "Environment=staging BedrockModelId=<model>"

# 4. smoke
python scripts/smoke.py --env staging

# 5. frontend
cd frontend && npm ci && npm run build
aws s3 sync dist s3://<web-bucket> --delete
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```

Expected first-run issues (we looked for these in the template):
- **CloudFront invalidation takes minutes** — the smoke test targets the API, not the website.
- **SES is sandboxed by default** — SNS email subscriptions need a verified identity or a support request; the code logs a warning and stores the subscription anyway.
- **OpenSearch domain sizing** — `t3.small.search` is the demo size; prod needs a standby node.
- **Canary rollback alarm** — the API error alarm must exist *before* the first deploy or `DeploymentPreference` fails.

## Phase 6 — Lessons for the next engineer

1. `cfn-lint` and `sam validate` catch real bugs — run them per-change, not per-release.
2. Credentials fail in confusing ways (`expiresIn`) — isolate them from tests.
3. Health checks lie: poll service endpoints yourself before declaring a container up.
4. LocalStack ≠ AWS: SNS email confirmation, SES sandboxing and CloudFront timings are only observable in the real account.
5. Every "verified locally" claim needs the command and its output; everything else is needs-deploy.
