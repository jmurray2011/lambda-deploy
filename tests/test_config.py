"""Tests for LAMBDA_DEPLOY config contract."""

from __future__ import annotations

from config import LAMBDA_DEPLOY_CONFIG


class TestConfig:
    def test_all_states_have_timeouts(self):
        for state in LAMBDA_DEPLOY_CONFIG.states:
            assert state in LAMBDA_DEPLOY_CONFIG.timeouts

    def test_all_states_have_rollback(self):
        for state in LAMBDA_DEPLOY_CONFIG.states:
            assert state in LAMBDA_DEPLOY_CONFIG.rollback

    def test_all_states_have_locks(self):
        for state in LAMBDA_DEPLOY_CONFIG.states:
            assert state in LAMBDA_DEPLOY_CONFIG.locks

    def test_timeout_ordering(self):
        for state, tc in LAMBDA_DEPLOY_CONFIG.timeouts.items():
            assert tc.soft < tc.hard < tc.ceiling

    def test_job_type(self):
        assert LAMBDA_DEPLOY_CONFIG.job_type == "LAMBDA_DEPLOY"

    def test_version(self):
        assert LAMBDA_DEPLOY_CONFIG.version == "1.0.0"
