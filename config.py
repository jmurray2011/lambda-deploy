"""Configuration for the LAMBDA_DEPLOY job."""

from detent.config import Compensating, JobConfig, ResourceLock, StateConfig

LAMBDA_DEPLOY_CONFIG = JobConfig(
    job_type="LAMBDA_DEPLOY",
    version="1.0.0",
    states=["INITIATED", "PUBLISHING", "UPDATING_ALIAS", "SMOKE_TESTING"],
    timeouts={
        "INITIATED": StateConfig(30, 120, 300),
        "PUBLISHING": StateConfig(30, 120, 300),
        "UPDATING_ALIAS": StateConfig(30, 120, 300),
        "SMOKE_TESTING": StateConfig(60, 300, 600),
    },
    rollback={
        "INITIATED": Compensating("compensate_noop"),
        "PUBLISHING": Compensating("compensate_noop"),
        "UPDATING_ALIAS": Compensating("compensate_revert_alias"),
        "SMOKE_TESTING": Compensating("compensate_revert_alias"),
    },
    locks={
        "INITIATED": [],
        "PUBLISHING": [
            ResourceLock("lambda:version:{params.function_name}"),
        ],
        "UPDATING_ALIAS": [
            ResourceLock(
                "lambda:alias:{params.function_name}:{params.alias_name}"
            ),
        ],
        "SMOKE_TESTING": [
            ResourceLock(
                "lambda:alias:{params.function_name}:{params.alias_name}"
            ),
        ],
    },
)
