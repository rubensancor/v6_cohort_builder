"""Data-extraction entrypoint: generate the cohort at an OMOP node.

Why this is a data-extraction step and not a federated one
----------------------------------------------------------
vantage6 5 hands a task the node's database connection — DATABASE_URI and the
DB_PARAM_* variables — only when the task's action is ``data_extraction``.
Federated and central compute steps run without any database access, by
design: they are meant to work on dataframes the extraction step produced.

The original ``generate_cohort_count`` was decorated ``@federated`` and so
never received the OMOP credentials; every node answered "Missing required
OMOP configuration". Moving the work here fixes that. The function still does
exactly what it did — CirceR turns ATLAS JSON into SQL, CohortGenerator writes
``results.cohort``, the count is read back — but it returns the outcome as a
one-row dataframe, which is what an extraction step must produce.

The row travels back to the client through ``cohort_count`` (federated.py),
which simply reads it. Orchestration across nodes happens client-side: the
in-container AlgorithmClient can only create federated tasks, so a central
function cannot trigger extractions (see central.py).
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

import pandas as pd

from .cohort import (
    CohortInputError,
    OmopConfig,
    atlas_json_to_sql,
    cohort_result_row,
    execute_cohort_generation,
    parse_omop_config,
    validate_cohort_request,
)

DecoratedFunction = TypeVar("DecoratedFunction", bound=Callable[..., Any])


try:
    from vantage6.algorithm.decorator.action import data_extraction
    from vantage6.algorithm.tools.util import info
except ValueError as exc:  # rpy2 without R at import time, e.g. in unit tests
    if "r_home is None" not in str(exc):
        raise

    def data_extraction(func: DecoratedFunction) -> DecoratedFunction:
        return func

    def info(message: str) -> None:
        print(message)


def _run_generate_cohort(
    cohort_name: str,
    sql: str | None = None,
    atlas_json: str | dict[str, Any] | None = None,
    cohort_id: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate the cohort and describe the outcome as a flat dict.

    Errors are reported inside the row rather than raised: an extraction step
    that raises produces no dataframe at all, and the client would then only
    learn that the run crashed, not why.
    """
    config: OmopConfig | None = None
    request = None
    try:
        request = validate_cohort_request(
            cohort_name=cohort_name,
            sql=sql,
            atlas_json=atlas_json,
            cohort_id=cohort_id,
            overwrite=overwrite,
        )
        config = parse_omop_config()

        cohort_sql = request.sql
        if request.atlas_json is not None:
            info("Converting ATLAS JSON to OHDSI CohortGenerator SQL")
            cohort_sql = atlas_json_to_sql(request.atlas_json)

        info(f"Generating cohort {request.cohort_id} '{request.cohort_name}'")
        outcome = execute_cohort_generation(
            config=config,
            sql=cohort_sql,
            cohort_name=request.cohort_name,
            cohort_id=request.cohort_id,
            overwrite=request.overwrite,
        )
        info(f"Cohort {request.cohort_id} holds {outcome['count']} subjects")
        return cohort_result_row(
            config=config,
            cohort_id=request.cohort_id,
            cohort_name=request.cohort_name,
            input_type=request.input_type,
            status="success",
            **outcome,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return cohort_result_row(
            config=config,
            cohort_id=request.cohort_id if request else cohort_id,
            cohort_name=cohort_name,
            input_type=request.input_type if request else None,
            status="error",
            message=str(exc),
        )


@data_extraction
def generate_cohort(
    connection_details: dict,
    cohort_name: str,
    sql: str | None = None,
    atlas_json: str | dict[str, Any] | None = None,
    cohort_id: int | None = None,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Generate a cohort in this node's OMOP database and return its count.

    ``connection_details`` is supplied by the node; the OMOP parameters are also
    available as DB_PARAM_* variables, which is what ``parse_omop_config`` reads.
    Provide exactly one of ``sql`` or ``atlas_json``.
    """
    del connection_details  # parse_omop_config reads the same values from the env
    row = _run_generate_cohort(
        cohort_name=cohort_name,
        sql=sql,
        atlas_json=atlas_json,
        cohort_id=cohort_id,
        overwrite=overwrite,
    )
    return pd.DataFrame([row])
