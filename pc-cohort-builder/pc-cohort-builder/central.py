"""
Central cohort builder entrypoint.

The central node validates cohort input, converts ATLAS JSON to OHDSI
CohortGenerator SQL when needed, dispatches cohort generation to all
organizations, and aggregates exact patient counts.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from vantage6.algorithm.client import AlgorithmClient
from vantage6.algorithm.tools.util import info

from .cohort import (
    aggregate_central_results,
    atlas_json_to_sql,
    validate_cohort_request,
)

DecoratedFunction = TypeVar("DecoratedFunction", bound=Callable[..., Any])


try:
    from vantage6.algorithm.decorator.action import central
    from vantage6.algorithm.decorator.algorithm_client import algorithm_client
except ValueError as exc:
    if "r_home is None" not in str(exc):
        raise

    def central(func: DecoratedFunction) -> DecoratedFunction:
        return func

    def algorithm_client(func: DecoratedFunction) -> DecoratedFunction:
        return func


def _run_central_function(
    client: AlgorithmClient,
    cohort_name: str,
    sql: str | None = None,
    atlas_json: str | dict[str, Any] | None = None,
    cohort_id: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    request = validate_cohort_request(
        cohort_name=cohort_name,
        sql=sql,
        atlas_json=atlas_json,
        cohort_id=cohort_id,
        overwrite=overwrite,
    )

    cohort_sql = request.sql
    if request.atlas_json is not None:
        info("Converting ATLAS JSON to OHDSI CohortGenerator SQL")
        cohort_sql = atlas_json_to_sql(request.atlas_json)

    organizations = client.organization.list()
    org_ids = [organization["id"] for organization in organizations]

    info(f"Creating cohort generation subtask for organizations {org_ids}")
    task = client.task.create(
        method="generate_cohort_count",
        arguments={
            "sql": cohort_sql,
            "cohort_name": request.cohort_name,
            "cohort_id": request.cohort_id,
            "overwrite": request.overwrite,
        },
        organizations=org_ids,
        name=f"Generate cohort {request.cohort_name}",
        description=f"Generate OMOP cohort {request.cohort_id} and return patient count",
    )

    info("Waiting for federated cohort counts")
    results = client.wait_for_results(task_id=task["id"])

    return aggregate_central_results(
        cohort_id=request.cohort_id,
        cohort_name=request.cohort_name,
        input_type=request.input_type,
        expected_org_ids=org_ids,
        raw_results=results,
    )


@central
@algorithm_client
def central_function(
    client: AlgorithmClient,
    cohort_name: str,
    sql: str | None = None,
    atlas_json: str | dict[str, Any] | None = None,
    cohort_id: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate a cohort at all federated OMOP nodes and return counts."""
    return _run_central_function(
        client=client,
        cohort_name=cohort_name,
        sql=sql,
        atlas_json=atlas_json,
        cohort_id=cohort_id,
        overwrite=overwrite,
    )
