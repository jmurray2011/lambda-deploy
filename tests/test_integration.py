"""Integration tests — run against LocalStack.

Requires:
    - LocalStack running (docker compose up from detent-infra)
    - test-function Lambda created (dev/seed/03-lambda.sh)
"""

from __future__ import annotations

import pytest

from detent.aws import get_client
from detent.db.audit import query_audit
from detent.db.operations import get_operation

from job import LambdaDeployJob
from params import LambdaDeployParams


@pytest.mark.integration
class TestIntegrationLifecycle:
    def test_launch_and_advance_through_publishing(self):
        """Launch and advance through the first two stages."""
        job = LambdaDeployJob()
        op_id = job.launch(
            LambdaDeployParams(function_name="test-function"),
        )

        op = get_operation(op_id)
        assert op is not None
        assert op["status"] == "INITIATED"
        assert op["jobType"] == "LAMBDA_DEPLOY"

        # Advance: INITIATED -> PUBLISHING
        job.advance(op_id)
        op = get_operation(op_id)
        assert op["status"] == "PUBLISHING"

        # Advance: PUBLISHING -> UPDATING_ALIAS
        job.advance(op_id)
        op = get_operation(op_id)
        assert op["status"] == "UPDATING_ALIAS"
        assert op["metadata"]["published_version"] is not None

        # Advance: UPDATING_ALIAS -> SMOKE_TESTING
        job.advance(op_id)
        op = get_operation(op_id)
        assert op["status"] == "SMOKE_TESTING"

        # Advance: SMOKE_TESTING -> DONE
        # LocalStack Lambda invoke returns 200 by default
        job.advance(op_id)
        op = get_operation(op_id)
        assert op["status"] == "DONE"

        # Verify audit trail exists
        audit = query_audit(op_id)
        assert len(audit) > 0

        # Verify alias was created in LocalStack
        client = get_client("lambda")
        alias = client.get_alias(
            FunctionName="test-function", Name="live",
        )
        assert alias["FunctionVersion"] == op["metadata"]["published_version"]

    def test_idempotency_after_terminal(self):
        """After an operation reaches DONE, a new launch should work
        since set_terminal releases the idempotency lock."""
        job = LambdaDeployJob()
        params = LambdaDeployParams(
            function_name="test-function", alias_name="idempotency-test",
        )

        op_id_1 = job.launch(params)
        for _ in range(4):
            job.advance(op_id_1)

        op = get_operation(op_id_1)
        assert op["status"] == "DONE"

        # Should be able to relaunch with same params
        op_id_2 = job.launch(params)
        assert op_id_2 != op_id_1
