"""Shared fixtures for lambda-deploy tests."""

from __future__ import annotations

import os
import sys

# Add project root so tests can import config, params, job
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import io  # noqa: E402
import json  # noqa: E402
import zipfile  # noqa: E402

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402


@pytest.fixture(autouse=True)
def _localstack_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point all AWS calls at LocalStack unless already configured."""
    if "AWS_ENDPOINT_URL" not in os.environ:
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")


@pytest.fixture()
def moto_aws(monkeypatch: pytest.MonkeyPatch):
    """Use moto mock instead of LocalStack."""
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        yield


@pytest.fixture()
def dynamodb_tables(moto_aws):
    """Create all three DynamoDB tables in moto."""
    from detent.alerter.publisher import _topic_arn_cache
    _topic_arn_cache.clear()

    ddb = boto3.resource("dynamodb", region_name="us-east-1")

    ddb.create_table(
        TableName="detent-operations",
        KeySchema=[{"AttributeName": "operationId", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "operationId", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "updatedAt", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "status-updatedAt-index",
            "KeySchema": [
                {"AttributeName": "status", "KeyType": "HASH"},
                {"AttributeName": "updatedAt", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )

    ddb.create_table(
        TableName="detent-audit",
        KeySchema=[
            {"AttributeName": "operationId", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "operationId", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    ddb.create_table(
        TableName="detent-locks",
        KeySchema=[{"AttributeName": "lock_key", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "lock_key", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    yield ddb


@pytest.fixture()
def sns_topics(moto_aws):
    """Create all SNS topics in moto."""
    from detent.alerter.publisher import _topic_arn_cache
    _topic_arn_cache.clear()

    sns = boto3.client("sns", region_name="us-east-1")
    sns.create_topic(Name="detent-ops-events")
    sns.create_topic(Name="detent-ops-alerts")
    sns.create_topic(Name="detent-watcher-trigger")
    yield sns


@pytest.fixture()
def lambda_function(moto_aws):
    """Create a minimal Lambda function in moto for testing."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr(
            "handler.py",
            (
                "def handler(event, context):\n"
                "    return {'statusCode': 200, 'body': 'ok'}\n"
            ),
        )
    zip_buffer.seek(0)

    iam = boto3.client("iam", region_name="us-east-1")
    iam.create_role(
        RoleName="test-lambda-role",
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        }),
        Path="/",
    )

    client = boto3.client("lambda", region_name="us-east-1")
    client.create_function(
        FunctionName="test-function",
        Runtime="python3.10",
        Role="arn:aws:iam::123456789012:role/test-lambda-role",
        Handler="handler.handler",
        Code={"ZipFile": zip_buffer.read()},
    )

    yield client
