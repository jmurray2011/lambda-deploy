#!/bin/bash
# Seed LocalStack with resources needed by the lambda-deploy job.
# Run after detent-infra seeds have created the framework tables/topics.
set -euo pipefail

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
AWS="aws --endpoint-url=$ENDPOINT"

echo "[lambda-deploy] Creating test Lambda function..."

TMPDIR=$(mktemp -d)
cat > "$TMPDIR/handler.py" << 'PYEOF'
def handler(event, context):
    return {"statusCode": 200, "body": "ok"}
PYEOF

cd "$TMPDIR" && zip -q handler.zip handler.py

$AWS iam create-role \
  --role-name test-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || true

$AWS lambda create-function \
  --function-name test-function \
  --runtime python3.10 \
  --role arn:aws:iam::000000000000:role/test-lambda-role \
  --handler handler.handler \
  --zip-file "fileb://$TMPDIR/handler.zip" \
  2>/dev/null || true

rm -rf "$TMPDIR"

# Register this job's route with the SQS trigger Lambda
echo "[lambda-deploy] Registering job route..."
CURRENT=$(
  $AWS lambda get-function-configuration \
    --function-name detent-sqs-trigger \
    --query 'Environment.Variables.JOB_ROUTES' \
    --output text 2>/dev/null || echo "{}"
)
[ "$CURRENT" = "None" ] && CURRENT="{}"

UPDATED=$(python3 -c "
import json, sys
routes = json.loads('$CURRENT')
routes['LAMBDA_DEPLOY'] = 'lambda-deploy/watcher'
print(json.dumps(routes))
")

$AWS lambda update-function-configuration \
  --function-name detent-sqs-trigger \
  --environment "Variables={JENKINS_URL=${JENKINS_URL:-http://jenkins:8080},JENKINS_USER=${JENKINS_USER:-admin},JENKINS_TOKEN=${JENKINS_TOKEN:-admin},JOB_ROUTES=$UPDATED}" \
  --output text --query 'FunctionName' 2>/dev/null || true

echo "[lambda-deploy] Seed complete."
