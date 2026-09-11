import importlib

import pytest


cohort = importlib.import_module("pc-cohort-builder.cohort")
federated = importlib.import_module("pc-cohort-builder.federated")


def test_run_generate_cohort_count_returns_success_payload(monkeypatch):
    config = cohort.OmopConfig(
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

    monkeypatch.setattr(federated, "parse_omop_config", lambda: config)
    monkeypatch.setattr(
        federated,
        "execute_cohort_generation",
        lambda config, sql, cohort_name, cohort_id, overwrite: {
            "database": config.cdm_database,
            "cdm_schema": config.cdm_schema,
            "results_schema": config.results_schema,
            "count": 42,
        },
    )

    result = federated._run_generate_cohort_count(
        sql="select * from cohort_sql",
        cohort_name="Death cohort",
        cohort_id=55,
        overwrite=True,
    )

    assert result == {
        "organization_id": 3,
        "node_id": 9,
        "status": "success",
        "cohort_id": 55,
        "cohort_name": "Death cohort",
        "database": "omop_cdm",
        "cdm_schema": "cdm",
        "results_schema": "results",
        "count": 42,
    }


def test_run_generate_cohort_count_returns_error_payload_when_config_raises(monkeypatch):
    monkeypatch.setattr(
        federated,
        "parse_omop_config",
        lambda: (_ for _ in ()).throw(cohort.NodeConfigError("missing password")),
    )

    result = federated._run_generate_cohort_count(
        sql="select * from cohort_sql",
        cohort_name="Death cohort",
        cohort_id=55,
    )

    assert result == {
        "organization_id": None,
        "node_id": None,
        "status": "error",
        "cohort_id": 55,
        "cohort_name": "Death cohort",
        "message": "missing password",
    }


def test_run_generate_cohort_count_returns_error_payload_when_execution_raises(monkeypatch):
    config = cohort.OmopConfig(
        uri="jdbc:postgresql://db:5432/omop",
        database_type="OMOP",
        dbms="postgresql",
        user="user",
        password="secret",
        cdm_database="omop",
        cdm_schema="cdm",
        results_schema="results",
        organization_id=3,
        node_id=9,
    )

    monkeypatch.setattr(federated, "parse_omop_config", lambda: config)
    monkeypatch.setattr(
        federated,
        "execute_cohort_generation",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("cohort exists")),
    )

    result = federated._run_generate_cohort_count(
        sql="select * from cohort_sql",
        cohort_name="Death cohort",
        cohort_id=55,
    )

    assert result == {
        "organization_id": 3,
        "node_id": 9,
        "status": "error",
        "cohort_id": 55,
        "cohort_name": "Death cohort",
        "message": "cohort exists",
    }


def test_generate_cohort_count_delegates_to_runner(monkeypatch):
    calls = []

    def fake_run(sql, cohort_name, cohort_id, overwrite=False):
        calls.append((sql, cohort_name, cohort_id, overwrite))
        return {"status": "success"}

    monkeypatch.setattr(federated, "_run_generate_cohort_count", fake_run)

    generate_cohort_count = getattr(
        federated.generate_cohort_count, "__wrapped__", federated.generate_cohort_count
    )

    assert generate_cohort_count("sql", "Cohort", 7, overwrite=True) == {
        "status": "success"
    }
    assert calls == [("sql", "Cohort", 7, True)]
