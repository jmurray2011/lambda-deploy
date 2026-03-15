"""Tests for LambdaDeployParams."""

from __future__ import annotations

from params import LambdaDeployParams


class TestDefaults:
    def test_default_values(self):
        p = LambdaDeployParams()
        assert p.function_name == ""
        assert p.alias_name == "live"
        assert p.test_payload == "{}"
        assert p.expected_status_code == 200
        assert p.dry_run is False

    def test_custom_values(self):
        p = LambdaDeployParams(
            function_name="my-func",
            alias_name="staging",
            test_payload='{"key": "val"}',
            expected_status_code=202,
            dry_run=True,
        )
        assert p.function_name == "my-func"
        assert p.alias_name == "staging"
        assert p.dry_run is True
