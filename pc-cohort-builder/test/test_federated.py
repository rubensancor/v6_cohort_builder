"""Tests for the vantage6 5 entry points.

Cohort generation now runs as a data-extraction step (extract.py) because
that is the only step vantage6 5 gives database access to; the federated step
(federated.py) only reads the resulting row back. Both are exercised here with
the OHDSI calls stubbed out, so the tests need neither R nor a database.
"""

import importlib

import pandas as pd
import pytest


cohort = importlib.import_module("pc-cohort-builder.cohort")
extract = importlib.import_module("pc-cohort-builder.extract")
federated = importlib.import_module("pc-cohort-builder.federated")


def undecorated(func):
    """The vantage6 decorators validate FUNCTION_ACTION and the node's
    environment; the tests want the function underneath them."""
    return getattr(func, "__wrapped__", func)


def _config() -> "cohort.OmopConfig":
    return cohort.OmopConfig(
        uri="jdbc:postgresql://db:5432/omop",
        database_type="OMOP",
        dbms="postgresql",
        user="omop_admin",
        password="change-me-before-deploying",
        cdm_database="omop_cdm",
        cdm_schema="cdm",
        results_schema="results",
        organization_id=3,
        node_id=9,
    )


def test_generate_cohort_returns_success_row(monkeypatch):
    monkeypatch.setattr(extract, "parse_omop_config", _config)
    monkeypatch.setattr(
        extract,
        "execute_cohort_generation",
        lambda config, sql, cohort_name, cohort_id, overwrite: {
            "database": config.cdm_database,
            "cdm_schema": config.cdm_schema,
            "results_schema": config.results_schema,
            "count": 42,
        },
    )

    row = extract._run_generate_cohort(
        sql="select * from cohort_sql",
        cohort_name="Death cohort",
        cohort_id=55,
        overwrite=True,
    )

    assert row == {
        "organization_id": 3,
        "node_id": 9,
        "status": "success",
        "cohort_id": 55,
        "cohort_name": "Death cohort",
        "input_type": "sql",
        "database": "omop_cdm",
        "cdm_schema": "cdm",
        "results_schema": "results",
        "count": 42,
        "message": None,
    }


def test_generate_cohort_converts_atlas_json_before_generating(monkeypatch):
    seen = {}
    monkeypatch.setattr(extract, "parse_omop_config", _config)
    monkeypatch.setattr(extract, "atlas_json_to_sql", lambda atlas: "SELECT 1 -- from atlas")

    def fake_execute(config, sql, cohort_name, cohort_id, overwrite):
        seen["sql"] = sql
        return {"count": 7}

    monkeypatch.setattr(extract, "execute_cohort_generation", fake_execute)

    row = extract._run_generate_cohort(
        cohort_name="Atlas cohort",
        atlas_json={"ConceptSets": []},
        cohort_id=1,
    )

    assert seen["sql"] == "SELECT 1 -- from atlas"
    assert row["input_type"] == "atlas_json"
    assert row["count"] == 7


def test_generate_cohort_reports_config_errors_in_the_row(monkeypatch):
    monkeypatch.setattr(
        extract,
        "parse_omop_config",
        lambda: (_ for _ in ()).throw(cohort.NodeConfigError("missing password")),
    )

    row = extract._run_generate_cohort(
        sql="select 1", cohort_name="Death cohort", cohort_id=55
    )

    # An extraction step that raises leaves no dataframe behind, so the
    # failure has to travel inside the row.
    assert row["status"] == "error"
    assert row["cohort_id"] == 55
    assert "missing password" in row["message"]
    assert row["organization_id"] is None


def test_generate_cohort_reports_execution_errors_in_the_row(monkeypatch):
    monkeypatch.setattr(extract, "parse_omop_config", _config)
    monkeypatch.setattr(
        extract,
        "execute_cohort_generation",
        lambda **_: (_ for _ in ()).throw(RuntimeError("cohort already exists")),
    )

    row = extract._run_generate_cohort(
        sql="select 1", cohort_name="Death cohort", cohort_id=55
    )

    assert row["status"] == "error"
    assert row["organization_id"] == 3
    assert "cohort already exists" in row["message"]


def test_generate_cohort_rejects_invalid_requests_in_the_row(monkeypatch):
    monkeypatch.setattr(extract, "parse_omop_config", _config)

    row = extract._run_generate_cohort(cohort_name="", sql="select 1", cohort_id=1)

    assert row["status"] == "error"
    assert "cohort_name" in row["message"]


def test_generate_cohort_wraps_the_row_in_a_dataframe(monkeypatch):
    monkeypatch.setattr(
        extract, "_run_generate_cohort",
        lambda **kw: {"status": "success", "count": 3, "cohort_id": kw["cohort_id"]},
    )

    frame = undecorated(extract.generate_cohort)(
        {"uri": "jdbc:postgresql://db/omop"}, cohort_name="c", sql="select 1", cohort_id=9
    )

    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 1
    assert frame.iloc[0]["count"] == 3


def test_cohort_count_returns_the_extracted_row_as_plain_json():
    frame = pd.DataFrame([{
        "organization_id": 3, "status": "success", "cohort_id": 55, "count": 42,
        "message": None,
    }])

    result = federated._run_cohort_count(frame)

    assert result["count"] == 42
    assert result["organization_id"] == 3
    # numpy scalars must not leak into the JSON result.
    assert type(result["count"]) is int
    assert result["message"] is None


def test_cohort_count_handles_an_empty_session():
    result = federated._run_cohort_count(pd.DataFrame())

    assert result["status"] == "error"


def test_legacy_generate_cohort_count_explains_why_it_cannot_run():
    result = undecorated(federated.generate_cohort_count)(
        sql="select 1", cohort_name="c", cohort_id=1
    )

    assert result["status"] == "error"
    assert "generate_cohort" in result["message"]


def test_normalize_jdbc_uri_completes_host_only_uris():
    assert (
        cohort.normalize_jdbc_uri("jdbc:postgresql://omop-postgres.omop.svc", "omop_cdm")
        == "jdbc:postgresql://omop-postgres.omop.svc:5432/omop_cdm"
    )
    assert (
        cohort.normalize_jdbc_uri("jdbc:postgresql://db:5433/other", "omop_cdm")
        == "jdbc:postgresql://db:5433/other"
    )
