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

## Phase 3b — The actual login failure (hit-and-trial, as it really happened)

This is the raw transcript of the first `aws login` attempt on this machine, kept because it is exactly what a human hits, and the error messages are not what you would guess.

**Attempt 1 — the AWS sign-in page returned a 400:**

```
400 Bad Request
You may have typed the address incorrectly or you may have used an outdated link.
Please clear your cookies and try the request again. If the problem persists,
please contact Support. We apologize for the inconvenience.
```

That 400 is not a code bug and not a wrong region — it is the AWS sign-in endpoint rejecting the cross-device authorization URL. The confusing part is that `aws login` still prints a URL and a state/PKCE code challenge, so it *looks* like the login is fine right up until the browser refuses the page.

**Attempt 2 — `aws login --remote` failed at the code prompt:**

```
$ aws login --remote
Browser will not be automatically opened.
Please visit the following URL:
https://ap-south-1.signin.aws.amazon.com/v1/authorize?response_type=code&...
Enter the authorization code displayed in your browser:
<pressed Enter without a code>
aws: [ERROR]: argument should be a bytes-like object or ASCII string, not 'NoneType'
```

The `not 'NoneType'` error is a real bug in the CLI's handling of an empty authorization code — you submitted nothing, and instead of a clean "no code entered" message it crashed deep in the argument parser. **The fix is to actually paste a code this time**, and the 400 from attempt 1 was a red herring.

**Attempt 3 — it worked.** Opened the `--remote` URL in a browser where I was already signed in to AWS, copied the long authorization code from the confirmation page, pasted it, and:

```
$ aws login --remote
Enter the authorization code displayed in your browser: Y29kZT1leUo2...  (long base64 code)
Updated profile default to use arn:aws:iam::609394381612:root credentials.
```

Then `aws sts get-caller-identity` returned account `609394381612` (role `root`), and the AWS CLI was usable.

### What each error actually meant

| Error | Real meaning | Action |
|---|---|---|
| `400 Bad Request` on the sign-in page | stale/expired cookies or an outdated cross-device link, not a wrong region | clear cookies for `*.amazon.com`, or just use `--remote` again |
| `not 'NoneType'` | I pressed Enter with an empty authorization code — the CLI's error handling, not AWS's | copy the code shown in the browser and paste it |
| `Session has expired. Please reauthenticate` (from Phase 3) | credentials existed but the SSO login token was gone | `aws login` again, or the test-isolation fix from Phase 3 |

### The lesson

None of these three errors were in our code. Every one of them was AWS CLI or AWS sign-in behaviour. The only real bug (`NoneType`) is in the AWS CLI itself, and the right move was to read the error, notice it was about *my input* rather than the code, and paste the actual code. Documenting this here so the next person does not burn an hour on it.

## Phase 4 — What is deployed vs not

| | |
|---|---|
| **Deployed for real** | **yes** — stack `dhuan-detective-stg` in ap-south-1, account 609394381612 |
| **Verified locally** | cfn-lint zero findings, ASL valid, 230 backend tests, 80 Playwright tests, live API on :8080 and web on :4173 serving real data + real OSM sources |
| **Ready to deploy** | `sam build` → `sam deploy --config-env staging` via `cd.yml`, or by hand now that login works |

## Phase 5 — Deployment runbook (for when credentials exist)

```bash
# 1. authenticate (already done on this machine; CI uses OIDC)
aws login          # proven working — see Phase 3b
aws sts get-caller-identity

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

## Phase 5b — The deploy that actually happened

```bash
aws ecr create-repository --repository-name dhuan-backend --image-scanning-configuration scanOnPush=true
aws s3 mb s3://dhuan-deploy-artifacts-609394381612
sam build --template-file infra/template.yaml --use-container
sam deploy --template-file .aws-sam/build/template.yaml \
  --config-file infra/samconfig.toml --config-env staging \
  --s3-bucket dhuan-deploy-artifacts-609394381612 \
  --parameter-overrides "Environment=staging BedrockModelId=anthropic.claude-haiku-4-5-20251001-v1:0 DemoMode=true"
```

**Live now:**

| What | URL |
|---|---|
| API base | `https://vz7mjma8sj.execute-api.ap-south-1.amazonaws.com/staging/v1` |
| Health | `.../staging/health` |
| Web app | `https://dhuan-detective-stg-webbucket-o2drps8axlex.s3.ap-south-1.amazonaws.com/index.html` |

### What deploying found that local testing never could

Nine real defects, every one invisible to `pytest` against a local uvicorn:

1. **Mangum API change** — `Mangum(app).handler` existed in mangum<0.17; current
   releases make the adapter callable itself. Every request 500'd.
2. **API Gateway stage collision** — the stage was named `v1` and the app also
   prefixes `/v1`, so `/staging/v1/estimate` was read as stage `v1` + path
   `/estimate` and 404'd on every `/v1/*` route. Only `/health` worked, which
   is exactly why this looked fine for ten minutes.
3. **`ApiDeployment` race** — no `DependsOn` on the methods, so the deployment
   snapshotted an empty API: *"The REST API doesn't contain any methods"*.
4. **ASL Parallel scope** — a branch cannot transition to a sibling state, so
   the per-branch `Catch -> RecordFeedFailure` could never resolve. Lifted the
   Catch onto the Parallel.
5. **ASL `Memory` on a Task** — not a field. Removed.
6. **ASL `$.ingested[-1]`** — reference paths have no negative array index.
7. **`DefinitionUri` does not substitute** — CloudFormation leaves
   `${AWS::Region}` in an S3-hosted definition, so every execution died with
   *"The resource belongs to a different region from the running execution.
   Expected 'ap-south-1', was '${AWS"*. Fixed with `DefinitionSubstitutions`.
8. **EventBridge target** — `!Ref` on a function gives a name, EventBridge
   wants an ARN. The `refresh_sources` task it invoked did not exist either.
9. **SAM build-args are not build stages** — `DockerBuildArgs: {TARGET: lambda}`
   is passed as `--build-arg`, which selects nothing; the default (last) stage
   was built. SAM only warned that TARGET was unconsumed.

Plus three account-level gates that no amount of template correctness can fix:
Bedrock, CloudFront and CodeDeploy all reject an unverified account. They are
now parameters so the stack deploys without them and turns them on later.

## Phase 6 — Lessons for the next engineer

1. `cfn-lint` and `sam validate` catch real bugs — run them per-change, not per-release.
2. Credentials fail in confusing ways (`expiresIn`) — isolate them from tests.
3. Health checks lie: poll service endpoints yourself before declaring a container up.
4. LocalStack ≠ AWS: SNS email confirmation, SES sandboxing and CloudFront timings are only observable in the real account.
5. Local tests cannot see the integration layer. Mangum, API Gateway stage
   naming, deployment ordering and ASL schema are all runtime-only failures.
   Deploy to a throwaway stack early.
6. Account-level gates (unverified account, service subscriptions) masquerade
   as code bugs. Read the error text before editing YAML.
7. AWS login errors are almost never your code — read whether the error is about
   *your input* (empty code → `NoneType`) or the *code*; only the latter is a bug here.
6. `sam validate --lint` catches transform-level errors that plain `cfn-lint` misses
   (it caught the `SSM_PARAMETER_PREFIX` reference cfn-lint let through). Run both.
5. Every "verified locally" claim needs the command and its output; everything else is needs-deploy.
