#!/usr/bin/env bash
# Dhuan Detective — staging deployment.
#
# Prerequisites:
#   aws login                      # or CONFIGURE credentials for the deploy role
#   aws sso put-parameter ...      # or manually: /dhuan/openaq-api-key, /dhuan/firms-map-key
#
# Usage:  scripts/deploy_staging.sh [--skip-build]
set -euo pipefail

STACK="dhuan-detective-staging"
REGION="${AWS_REGION:-ap-south-1}"
WEB_BUCKET="${WEB_BUCKET:-}"          # set after the first deploy, or pass via env
CF_ID="${CF_ID:-}"                     # CloudFront distribution id

echo "==> 0. preflight"
aws sts get-caller-identity --no-cli-pager || {
  echo "ERROR: not authenticated. Run: aws login"
  exit 2
}
[[ -n "${BEDROCK_MODEL_ID:-}" ]] || {
  echo "ERROR: export BEDROCK_MODEL_ID=<a model available in ${REGION}>"
  exit 2
}

echo "==> 1. build the Lambda container image"
if [[ "${1:-}" != "--skip-build" ]]; then
  sam build --template infra/template.yaml --use-container
fi

echo "==> 2. deploy"
sam deploy \
  --config-file infra/samconfig.toml \
  --config-env staging \
  --no-confirm-changeset \
  --s3-bucket "${S3_DEPLOY_BUCKET:-}" \
  --region "${REGION}" \
  --parameter-overrides \
    "Environment=staging BedrockModelId=${BEDROCK_MODEL_ID} WebBucketName=${WEB_BUCKET:-DhuanWebPlaceholderChangeMe}"

echo "==> 3. resolve the API URL"
API_URL=$(aws cloudformation describe-stacks --stack-name "${STACK}" --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
echo "   API: ${API_URL}"
aws ssm put-parameter --name /dhuan/staging/api-url --type String --value "${API_URL}" \
  --overwrite --region "${REGION}" >/dev/null

echo "==> 4. seed OpenSearch sources (real OSM data)"
if [[ -n "${OPENSEARCH_ENDPOINT:-}" ]]; then
  (cd backend && OPENSEARCH_ENDPOINT="${OPENSEARCH_ENDPOINT}" uv run python -m dhuan.scripts.seed_local --all) || \
    echo "   WARNING: source seeding failed — see RUNBOOK"
else
  echo "   (set OPENSEARCH_ENDPOINT after the OpenSearch domain is created)"
fi

echo "==> 5. smoke test"
python scripts/smoke.py --env staging

echo "==> 6. frontend"
if [[ -n "${WEB_BUCKET}" && -n "${CF_ID}" ]]; then
  (cd frontend && npm ci && npm run build)
  aws s3 sync frontend/dist "s3://${WEB_BUCKET}" --delete
  aws cloudfront create-invalidation --distribution-id "${CF_ID}" --paths "/*" >/dev/null
  echo "   web deployed + invalidated"
else
  echo "   (set WEB_BUCKET and CF_ID to deploy the frontend)"
fi

echo "==> done"
echo "   API: ${API_URL}"
