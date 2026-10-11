#!/usr/bin/env bash
# Dhuan Detective teardown: remove everything this project created in AWS.
#
# Usage: scripts/teardown.sh [staging|prod]
set -euo pipefail

ENV_NAME="${1:-staging}"
STACK="dhuan-detective-${ENV_NAME}"
REGION="${AWS_REGION:-ap-south-1}"

echo "This will delete the CloudFormation stack '${STACK}' in ${REGION}."
echo "Everything created by infra/template.yaml for ${ENV_NAME} will be removed."
read -r -p "Type the stack name to confirm: " CONFIRM
if [[ "${CONFIRM}" != "${STACK}" ]]; then
  echo "aborted"
  exit 1
fi

echo "==> disabling CloudFront distribution termination protection (if any)"
DIST_IDS=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='dhuan-detective-web-${ENV_NAME}'].Id" \
  --output text 2>/dev/null || true)
for ID in ${DIST_IDS}; do
  echo "  distribution ${ID}: leaving to the stack (it is part of it)"
done

echo "==> deleting S3 website bucket contents (versioned objects included)"
WEB_BUCKET=$(aws s3api list-buckets --query "Buckets[?contains(Name, 'dhuan-web-${ENV_NAME}')].Name" --output text 2>/dev/null || true)
for B in ${WEB_BUCKET}; do
  echo "  emptying s3://${B}"
  aws s3 rm "s3://${B}" --recursive || true
  aws s3api delete-objects --bucket "${B}" \
    --delete "$(aws s3api list-object-versions --bucket "${B}" --query 'Versions[].{Key:Key,VersionId:VersionId}' --output json)" \
    >/dev/null 2>&1 || true
done

echo "==> deleting the stack"
aws cloudformation delete-stack --stack-name "${STACK}" --region "${REGION}"
aws cloudformation wait stack-delete-complete --stack-name "${STACK}" --region "${REGION}"

echo "==> verifying nothing remains"
LEFT=$(aws cloudformation describe-stacks --stack-name "${STACK}" --region "${REGION}" 2>&1 || true)
if echo "${LEFT}" | grep -q "does not exist"; then
  echo "teardown complete: ${STACK} removed"
else
  echo "WARNING: stack status: ${LEFT}"
  exit 1
fi
