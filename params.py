"""Parameters for the LAMBDA_DEPLOY job."""

from __future__ import annotations

from dataclasses import dataclass

from detent.params import JobParams


@dataclass
class LambdaDeployParams(JobParams):
    """Runtime inputs for a Lambda deployment."""

    function_name: str = ""
    alias_name: str = "live"
    test_payload: str = "{}"
    expected_status_code: int = 200
