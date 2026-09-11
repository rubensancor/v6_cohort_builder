"""Federated cohort generation entrypoints executed at OMOP nodes."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from .cohort import OmopConfig, execute_cohort_generation, parse_omop_config

DecoratedFunction = TypeVar("DecoratedFunction", bound=Callable[..., Any])


try:
    from vantage6.algorithm.decorator.action import federated
except ValueError as exc:
    if "r_home is None" not in str(exc):
        raise

    def federated(func: DecoratedFunction) -> DecoratedFunction:
        return func


def _run_generate_cohort_count(
    sql: str,
    cohort_name: str,
    cohort_id: int,
    overwrite: bool = False,
) -> dict[str, Any]:
    config: OmopConfig | None = None
    try:
        config = parse_omop_config()
        result = execute_cohort_generation(
            config=config,
            sql=sql,
            cohort_name=cohort_name,
            cohort_id=cohort_id,
            overwrite=overwrite,
        )
        return {
            "organization_id": config.organization_id,
            "node_id": config.node_id,
            "status": "success",
            "cohort_id": cohort_id,
            "cohort_name": cohort_name,
            **result,
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {
            "organization_id": config.organization_id if config is not None else None,
            "node_id": config.node_id if config is not None else None,
            "status": "error",
            "cohort_id": cohort_id,
            "cohort_name": cohort_name,
            "message": str(exc),
        }


@federated
def generate_cohort_count(
    sql: str,
    cohort_name: str,
    cohort_id: int,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate a cohort at this node and return its exact subject count."""
    return _run_generate_cohort_count(
        sql=sql,
        cohort_name=cohort_name,
        cohort_id=cohort_id,
        overwrite=overwrite,
    )
