"""Tests for LambdaDeployJob lifecycle."""

from __future__ import annotations

import pytest

from detent.db.exceptions import DuplicateOperationError
from detent.db.operations import get_operation

from job import LambdaDeployJob
from params import LambdaDeployParams


class TestLaunch:
    def test_creates_operation(
        self, dynamodb_tables, sns_topics, lambda_function,
    ):
        job = LambdaDeployJob()
        op_id = job.launch(
            LambdaDeployParams(function_name="test-function"),
        )
        op = get_operation(op_id)
        assert op is not None
        assert op["status"] == "INITIATED"
        assert op["jobType"] == "LAMBDA_DEPLOY"

    def test_duplicate_raises(
        self, dynamodb_tables, sns_topics, lambda_function,
    ):
        job = LambdaDeployJob()
        job.launch(LambdaDeployParams(function_name="test-function"))

        with pytest.raises(DuplicateOperationError):
            job.launch(LambdaDeployParams(function_name="test-function"))

    def test_different_alias_allowed(
        self, dynamodb_tables, sns_topics, lambda_function,
    ):
        job = LambdaDeployJob()
        op1 = job.launch(
            LambdaDeployParams(
                function_name="test-function", alias_name="live",
            ),
        )
        op2 = job.launch(
            LambdaDeployParams(
                function_name="test-function", alias_name="staging",
            ),
        )
        assert op1 != op2

    def test_empty_function_name_raises(
        self, dynamodb_tables, sns_topics,
    ):
        job = LambdaDeployJob()
        with pytest.raises(ValueError, match="function_name is required"):
            job.launch(LambdaDeployParams(function_name=""))


class TestFullLifecycle:
    def test_happy_path(
        self, dynamodb_tables, sns_topics, lambda_function,
    ):
        job = LambdaDeployJob()
        op_id = job.launch(
            LambdaDeployParams(function_name="test-function"),
        )

        job.advance(op_id)  # INITIATED -> PUBLISHING
        op = get_operation(op_id)
        assert op["status"] == "PUBLISHING"

        job.advance(op_id)  # PUBLISHING -> UPDATING_ALIAS
        op = get_operation(op_id)
        assert op["status"] == "UPDATING_ALIAS"
        assert "published_version" in op["metadata"]

        job.advance(op_id)  # UPDATING_ALIAS -> SMOKE_TESTING
        op = get_operation(op_id)
        assert op["status"] == "SMOKE_TESTING"
        assert "previous_version" in op["metadata"]

        # Stub smoke test since moto invoke requires docker
        def mock_smoke(record):
            return {"smoke_test_status": "passed"}

        job.stage_smoke_testing = mock_smoke  # type: ignore[assignment]
        job.advance(op_id)  # SMOKE_TESTING -> DONE

        op = get_operation(op_id)
        assert op["status"] == "DONE"
        assert op["metadata"]["smoke_test_status"] == "passed"

    def test_custom_alias(
        self, dynamodb_tables, sns_topics, lambda_function,
    ):
        job = LambdaDeployJob()
        op_id = job.launch(
            LambdaDeployParams(
                function_name="test-function",
                alias_name="staging",
            ),
        )

        for _ in range(3):
            job.advance(op_id)

        def mock_smoke(record):
            return {"smoke_test_status": "passed"}

        job.stage_smoke_testing = mock_smoke  # type: ignore[assignment]
        job.advance(op_id)

        op = get_operation(op_id)
        assert op["status"] == "DONE"


class TestRollback:
    def test_smoke_test_failure_reverts_alias(
        self, dynamodb_tables, sns_topics, lambda_function,
    ):
        job = LambdaDeployJob()
        op_id = job.launch(
            LambdaDeployParams(function_name="test-function"),
        )

        job.advance(op_id)  # -> PUBLISHING
        job.advance(op_id)  # -> UPDATING_ALIAS
        job.advance(op_id)  # -> SMOKE_TESTING

        def failing_smoke(record):
            raise RuntimeError("smoke test failed")

        job.stage_smoke_testing = failing_smoke  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="smoke test failed"):
            job.advance(op_id)

        op = get_operation(op_id)
        assert op["status"] == "FAILED"


class TestIdempotencyKey:
    def test_key_format(self):
        job = LambdaDeployJob()
        params = LambdaDeployParams(
            function_name="my-func", alias_name="live",
        )
        assert job.idempotency_key(params) == "LAMBDA_DEPLOY#my-func#live"

    def test_different_alias_different_key(self):
        job = LambdaDeployJob()
        k1 = job.idempotency_key(
            LambdaDeployParams(function_name="f", alias_name="live"),
        )
        k2 = job.idempotency_key(
            LambdaDeployParams(function_name="f", alias_name="staging"),
        )
        assert k1 != k2
