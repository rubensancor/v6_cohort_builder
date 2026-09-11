import importlib
import json

import pandas as pd
import pytest


cohort = importlib.import_module("pc-cohort-builder.cohort")


def test_validate_request_accepts_sql_and_generates_id():
    request = cohort.validate_cohort_request(
        cohort_name="Death cohort",
        sql="SELECT * FROM @cdm_database_schema.person;",
        cohort_id=None,
        atlas_json=None,
        overwrite=False,
        id_factory=lambda: 12345,
    )

    assert request.cohort_name == "Death cohort"
    assert request.sql == "SELECT * FROM @cdm_database_schema.person;"
    assert request.atlas_json is None
    assert request.input_type == "sql"
    assert request.cohort_id == 12345
    assert request.overwrite is False


def test_validate_request_accepts_atlas_json_dict():
    atlas_json = {"ConceptSets": [], "PrimaryCriteria": {"CriteriaList": []}}

    request = cohort.validate_cohort_request(
        cohort_name="Atlas cohort",
        sql=None,
        atlas_json=atlas_json,
        cohort_id=77,
        overwrite=True,
        id_factory=lambda: 12345,
    )

    assert request.sql is None
    assert json.loads(request.atlas_json) == atlas_json
    assert request.input_type == "atlas_json"
    assert request.cohort_id == 77
    assert request.overwrite is True


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (
            {"cohort_name": "", "sql": "select 1", "atlas_json": None},
            "cohort_name is required",
        ),
        (
            {"cohort_name": "x", "sql": None, "atlas_json": None},
            "Provide exactly one",
        ),
        (
            {"cohort_name": "x", "sql": "select 1", "atlas_json": {}},
            "Provide exactly one",
        ),
        (
            {"cohort_name": "x", "sql": " ", "atlas_json": None},
            "sql must be a non-empty string",
        ),
        (
            {"cohort_name": "x", "sql": "select 1", "atlas_json": None, "cohort_id": 0},
            "cohort_id must be a positive integer",
        ),
        (
            {"cohort_name": "x", "sql": "select 1", "atlas_json": None, "cohort_id": True},
            "cohort_id must be a positive integer",
        ),
        (
            {"cohort_name": "x", "sql": "select 1", "atlas_json": None, "overwrite": "yes"},
            "overwrite must be a boolean",
        ),
        (
            {"cohort_name": "x", "sql": None, "atlas_json": "{"},
            "atlas_json must be valid JSON",
        ),
    ],
)
def test_validate_request_rejects_invalid_inputs(kwargs, message):
    defaults = {
        "cohort_id": None,
        "overwrite": False,
        "id_factory": lambda: 12345,
    }
    defaults.update(kwargs)

    with pytest.raises(cohort.CohortInputError, match=message):
        cohort.validate_cohort_request(**defaults)


def test_normalize_atlas_json_reports_non_serializable_values():
    with pytest.raises(cohort.CohortInputError, match="atlas_json must be valid JSON"):
        cohort.normalize_atlas_json({"ConceptSets": [object()]})


def test_parse_omop_config_reads_vantage6_database_environment():
    env = {
        "DATABASE_URI": "jdbc:postgresql://db:5432/omop",
        "DATABASE_TYPE": "OMOP",
        "DB_PARAM_DBMS": "postgresql",
        "DB_PARAM_USER": "user",
        "DB_PARAM_PASSWORD": "secret",
        "DB_PARAM_CDM_DATABASE": "omop",
        "DB_PARAM_CDM_SCHEMA": "cdm",
        "DB_PARAM_RESULTS_SCHEMA": "results",
        "ORGANIZATION_ID": "3",
        "NODE_ID": "9",
    }

    config = cohort.parse_omop_config(env)

    assert config.uri == "jdbc:postgresql://db:5432/omop"
    assert config.database_type == "OMOP"
    assert config.dbms == "postgresql"
    assert config.user == "user"
    assert config.password == "secret"
    assert config.cdm_database == "omop"
    assert config.cdm_schema == "cdm"
    assert config.results_schema == "results"
    assert config.organization_id == 3
    assert config.node_id == 9


def test_parse_omop_config_reports_missing_keys():
    with pytest.raises(cohort.NodeConfigError, match="DB_PARAM_PASSWORD"):
        cohort.parse_omop_config(
            {
                "DATABASE_URI": "jdbc:postgresql://db:5432/omop",
                "DATABASE_TYPE": "OMOP",
                "DB_PARAM_DBMS": "postgresql",
                "DB_PARAM_USER": "user",
                "DB_PARAM_CDM_DATABASE": "omop",
                "DB_PARAM_CDM_SCHEMA": "cdm",
                "DB_PARAM_RESULTS_SCHEMA": "results",
            }
        )


def test_parse_omop_config_reports_invalid_optional_ids():
    with pytest.raises(cohort.NodeConfigError, match="ORGANIZATION_ID must be an integer"):
        cohort.parse_omop_config(
            {
                "DATABASE_URI": "jdbc:postgresql://db:5432/omop",
                "DATABASE_TYPE": "OMOP",
                "DB_PARAM_DBMS": "postgresql",
                "DB_PARAM_USER": "user",
                "DB_PARAM_PASSWORD": "secret",
                "DB_PARAM_CDM_DATABASE": "omop",
                "DB_PARAM_CDM_SCHEMA": "cdm",
                "DB_PARAM_RESULTS_SCHEMA": "results",
                "ORGANIZATION_ID": "abc",
            }
        )


def test_extract_subject_count_from_cohort_counts_dataframe():
    df = pd.DataFrame(
        {
            "cohortDefinitionId": [55],
            "numberRecords": [88],
            "numberSubjects": [42],
        }
    )

    assert cohort.extract_subject_count(df, 55) == 42


def test_extract_subject_count_accepts_alternate_column_names():
    df = pd.DataFrame(
        {
            "cohortId": [55],
            "subjectCount": ["42"],
        }
    )

    assert cohort.extract_subject_count(df, 55) == 42


def test_extract_subject_count_accepts_ohdsi_cohort_generator_columns():
    df = pd.DataFrame(
        {
            "cohortId": [55.0],
            "cohortEntries": [88.0],
            "cohortSubjects": [42.0],
        }
    )

    assert cohort.extract_subject_count(df, 55) == 42


def test_extract_subject_count_wraps_invalid_cohort_id_values():
    df = pd.DataFrame(
        {
            "cohortDefinitionId": ["not-an-id"],
            "numberSubjects": [42],
        }
    )

    with pytest.raises(cohort.CohortInputError, match="cohort id"):
        cohort.extract_subject_count(df, 55)


def test_extract_subject_count_wraps_invalid_subject_count_values():
    df = pd.DataFrame(
        {
            "cohortDefinitionId": [55],
            "numberSubjects": ["not-a-count"],
        }
    )

    with pytest.raises(cohort.CohortInputError, match="subject count"):
        cohort.extract_subject_count(df, 55)


def test_aggregate_results_returns_total_only_when_all_nodes_succeed():
    response = cohort.aggregate_central_results(
        cohort_id=55,
        cohort_name="Death cohort",
        input_type="sql",
        expected_org_ids=[1, 2],
        raw_results=[
            {
                "organization_id": 1,
                "status": "success",
                "count": 10,
                "database": "site_a",
                "cdm_schema": "cdm",
                "results_schema": "results",
            },
            {
                "organization_id": 2,
                "status": "success",
                "count": 12,
                "database": "site_b",
                "cdm_schema": "cdm",
                "results_schema": "results",
            },
        ],
    )

    assert response["total_count"] == 22
    assert response["errors"] == []
    assert response["nodes"] == [
        {
            "organization_id": 1,
            "status": "success",
            "count": 10,
            "database": "site_a",
            "cdm_schema": "cdm",
            "results_schema": "results",
        },
        {
            "organization_id": 2,
            "status": "success",
            "count": 12,
            "database": "site_b",
            "cdm_schema": "cdm",
            "results_schema": "results",
        },
    ]


def test_aggregate_results_keeps_partial_success_and_null_total():
    response = cohort.aggregate_central_results(
        cohort_id=55,
        cohort_name="Death cohort",
        input_type="sql",
        expected_org_ids=[1, 2, 3],
        raw_results=[
            {"organization_id": 1, "status": "success", "count": 10},
            {"organization_id": 2, "status": "error", "message": "conflict"},
        ],
    )

    assert response["total_count"] is None
    assert response["nodes"] == [{"organization_id": 1, "status": "success", "count": 10}]
    assert response["errors"] == [
        {"organization_id": 2, "status": "error", "message": "conflict"},
        {"organization_id": 3, "status": "error", "message": "No result returned by organization 3"},
    ]


def test_aggregate_results_handles_error_without_organization_id():
    response = cohort.aggregate_central_results(
        cohort_id=55,
        cohort_name="Death cohort",
        input_type="sql",
        expected_org_ids=[1],
        raw_results=[
            {
                "organization_id": None,
                "status": "error",
                "message": "missing password",
            }
        ],
    )

    assert response["nodes"] == []
    assert response["errors"] == [
        {"organization_id": None, "status": "error", "message": "missing password"},
        {
            "organization_id": 1,
            "status": "error",
            "message": "No result returned by organization 1",
        },
    ]
    assert response["total_count"] is None


def test_execute_cohort_generation_uses_ohdsi_wrappers_and_returns_count(monkeypatch):
    calls = []

    class FakeConnection:
        def execute(self, sql):
            calls.append(("execute", sql))
            return pd.DataFrame({"row_count": [0]})

    class FakeDatabaseConnector:
        def create_connection_details(self, **kwargs):
            calls.append(("create_connection_details", kwargs))
            return {"details": kwargs}

        def connect(self, connection_details):
            calls.append(("connect", connection_details))
            return FakeConnection()

        def disconnect(self, connection):
            calls.append(("disconnect", connection))

    class FakeCohortGenerator:
        def get_cohort_table_names(self):
            calls.append(("get_cohort_table_names",))
            return {"cohort": "cohort"}

        def create_cohort_tables(self, **kwargs):
            calls.append(("create_cohort_tables", kwargs))

        def generate_cohort_set(self, **kwargs):
            calls.append(("generate_cohort_set", kwargs))

        def get_cohort_counts(self, **kwargs):
            calls.append(("get_cohort_counts", kwargs))
            return "r-counts"

    class FakeCommon:
        def convert_to_r(self, value):
            calls.append(("convert_to_r", value))
            return "r-cohort-definition-set"

        def convert_from_r(self, value):
            calls.append(("convert_from_r", value))
            assert value == "r-counts"
            return pd.DataFrame(
                {
                    "cohortDefinitionId": [55],
                    "numberSubjects": [42],
                }
            )

    monkeypatch.setattr(
        cohort,
        "_load_ohdsi_modules",
        lambda: (FakeCommon(), FakeCohortGenerator(), FakeDatabaseConnector()),
    )
    config = cohort.OmopConfig(
        uri="jdbc:postgresql://db:5432/omop",
        database_type="OMOP",
        dbms="postgresql",
        user="user",
        password="secret",
        cdm_database="omop",
        cdm_schema="cdm",
        results_schema="results",
    )

    result = cohort.execute_cohort_generation(
        config=config,
        sql="select * from @cdm_database_schema.person",
        cohort_name="Death cohort",
        cohort_id=55,
        overwrite=False,
    )

    assert result == {
        "database": "omop",
        "cdm_schema": "cdm",
        "results_schema": "results",
        "count": 42,
    }
    assert calls[0] == (
        "create_connection_details",
        {
            "dbms": "postgresql",
            "connection_string": "jdbc:postgresql://db:5432/omop",
            "user": "user",
            "password": "secret",
        },
    )
    assert calls[1] == (
        "connect",
        {
            "details": {
                "dbms": "postgresql",
                "connection_string": "jdbc:postgresql://db:5432/omop",
                "user": "user",
                "password": "secret",
            }
        },
    )
    assert calls[2] == ("get_cohort_table_names",)
    assert calls[3][0] == "create_cohort_tables"
    assert calls[3][1]["connection"].__class__ is FakeConnection
    assert calls[3][1]["cohort_database_schema"] == "results"
    assert calls[3][1]["cohort_table_names"] == {"cohort": "cohort"}
    assert calls[4][0] == "execute"
    assert "results.cohort" in calls[4][1]
    assert "cohort_definition_id = 55" in calls[4][1]
    assert calls[5][0] == "convert_to_r"
    assert list(calls[5][1].columns) == ["cohortId", "cohortName", "sql"]
    assert calls[5][1].to_dict(orient="records") == [
        {
            "cohortId": 55,
            "cohortName": "Death cohort",
            "sql": "select * from @cdm_database_schema.person",
        }
    ]
    assert calls[6] == (
        "generate_cohort_set",
        {
            "connection_details": {
                "details": {
                    "dbms": "postgresql",
                    "connection_string": "jdbc:postgresql://db:5432/omop",
                    "user": "user",
                    "password": "secret",
                }
            },
            "cdm_database_schema": "cdm",
            "cohort_database_schema": "results",
            "cohort_table_names": {"cohort": "cohort"},
            "cohort_definition_set": "r-cohort-definition-set",
        },
    )
    assert calls[7] == (
        "get_cohort_counts",
        {
            "connection_details": {
                "details": {
                    "dbms": "postgresql",
                    "connection_string": "jdbc:postgresql://db:5432/omop",
                    "user": "user",
                    "password": "secret",
                }
            },
            "cohort_database_schema": "results",
            "cohort_table": "cohort",
            "cohort_ids": [55],
        },
    )
    assert calls[8] == ("convert_from_r", "r-counts")
    assert calls[9][0] == "disconnect"
