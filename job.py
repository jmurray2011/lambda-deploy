"""LAMBDA_DEPLOY job — deploy a new Lambda version via alias update."""

from __future__ import annotations

import logging
from typing import Any

from detent.aws import get_client
from detent.base_job import BaseJob
from detent.dry_run import is_dry_run
from detent.params import JobParams

from config import LAMBDA_DEPLOY_CONFIG

logger = logging.getLogger(__name__)


class LambdaDeployJob(BaseJob):
    """Deploy a new Lambda function version and update an alias."""

    config = LAMBDA_DEPLOY_CONFIG

    def idempotency_key(self, params: JobParams) -> str:
        p = params  # type: ignore[assignment]
        return f"LAMBDA_DEPLOY#{p.function_name}#{p.alias_name}"

    # --- Stage methods ---

    def stage_initiated(
        self, record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Validate params and verify the function exists."""
        metadata = record["metadata"]
        function_name = metadata["function_name"]

        if not function_name:
            raise ValueError("function_name is required")

        if is_dry_run():
            logger.info("DRY RUN: would validate function %s", function_name)
            return None

        client = get_client("lambda")
        client.get_function(FunctionName=function_name)
        return None

    def stage_publishing(
        self, record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Publish a new version from $LATEST."""
        metadata = record["metadata"]
        function_name = metadata["function_name"]

        if is_dry_run():
            logger.info(
                "DRY RUN: would publish version for %s", function_name,
            )
            return {"published_version": "dry-run"}

        client = get_client("lambda")
        response = client.publish_version(FunctionName=function_name)
        version = response["Version"]
        logger.info("Published version %s for %s", version, function_name)
        return {"published_version": version}

    def stage_updating_alias(
        self, record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update or create the alias to point to the new version."""
        metadata = record["metadata"]
        function_name = metadata["function_name"]
        alias_name = metadata["alias_name"]
        new_version = metadata["published_version"]

        if is_dry_run():
            logger.info(
                "DRY RUN: would update alias %s to version %s",
                alias_name, new_version,
            )
            return {"previous_version": "dry-run"}

        client = get_client("lambda")
        previous_version = None

        try:
            alias_info = client.get_alias(
                FunctionName=function_name, Name=alias_name,
            )
            previous_version = alias_info["FunctionVersion"]
            client.update_alias(
                FunctionName=function_name,
                Name=alias_name,
                FunctionVersion=new_version,
            )
            logger.info(
                "Updated alias %s: %s -> %s",
                alias_name, previous_version, new_version,
            )
        except client.exceptions.ResourceNotFoundException:
            client.create_alias(
                FunctionName=function_name,
                Name=alias_name,
                FunctionVersion=new_version,
            )
            logger.info(
                "Created alias %s -> %s", alias_name, new_version,
            )

        return {"previous_version": previous_version}

    def stage_smoke_testing(
        self, record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Invoke the function via alias and validate the response."""
        metadata = record["metadata"]
        function_name = metadata["function_name"]
        alias_name = metadata["alias_name"]
        test_payload = metadata.get("test_payload", "{}")
        expected_status = metadata.get("expected_status_code", 200)

        if is_dry_run():
            logger.info(
                "DRY RUN: would invoke %s:%s", function_name, alias_name,
            )
            return {"smoke_test_status": "skipped"}

        client = get_client("lambda")
        qualified = f"{function_name}:{alias_name}"

        response = client.invoke(
            FunctionName=qualified,
            Payload=test_payload.encode("utf-8"),
        )

        status_code = response["StatusCode"]
        payload_bytes = response["Payload"].read()

        if "FunctionError" in response:
            raise RuntimeError(
                f"Smoke test failed: function error "
                f"'{response['FunctionError']}'. "
                f"Response: {payload_bytes.decode('utf-8', errors='replace')}"
            )

        if status_code != expected_status:
            raise RuntimeError(
                f"Smoke test failed: expected {expected_status}, "
                f"got {status_code}. "
                f"Response: {payload_bytes.decode('utf-8', errors='replace')}"
            )

        logger.info(
            "Smoke test passed for %s:%s (status=%d)",
            function_name, alias_name, status_code,
        )
        return {
            "smoke_test_status": "passed",
            "smoke_test_response_status": status_code,
        }

    # --- Compensating actions ---

    def compensate_noop(self, record: dict[str, Any]) -> None:
        """No-op — nothing to undo for INITIATED or PUBLISHING."""
        logger.info("No-op compensating action")

    def compensate_revert_alias(self, record: dict[str, Any]) -> None:
        """Revert the alias to its previous version."""
        metadata = record.get("metadata", {})
        function_name = metadata["function_name"]
        alias_name = metadata["alias_name"]
        previous_version = metadata.get("previous_version")

        if previous_version is None:
            logger.info(
                "No previous version for alias %s — was newly created",
                alias_name,
            )
            return

        if is_dry_run():
            logger.info(
                "DRY RUN: would revert alias %s to %s",
                alias_name, previous_version,
            )
            return

        client = get_client("lambda")
        client.update_alias(
            FunctionName=function_name,
            Name=alias_name,
            FunctionVersion=previous_version,
        )
        logger.info(
            "Reverted alias %s to version %s", alias_name, previous_version,
        )
