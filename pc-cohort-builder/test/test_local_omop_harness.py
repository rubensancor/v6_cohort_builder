from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "local-omop"


def test_local_omop_compose_defines_postgres_service():
    compose = (HARNESS / "docker-compose.yml").read_text()

    assert "postgres:16" in compose
    assert "5433:5432" in compose
    assert "POSTGRES_DB: omop" in compose
    assert "./init:/docker-entrypoint-initdb.d:ro" in compose


def test_local_omop_schema_contains_minimal_cdm_and_results_schema():
    schema_sql = (HARNESS / "init" / "01_schema.sql").read_text()

    assert "CREATE SCHEMA IF NOT EXISTS cdm;" in schema_sql
    assert "CREATE SCHEMA IF NOT EXISTS results;" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS cdm.person" in schema_sql
    assert "person_id BIGINT PRIMARY KEY" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS cdm.observation_period" in schema_sql


def test_local_omop_seed_has_three_patients_born_after_1970():
    seed_sql = (HARNESS / "init" / "02_seed.sql").read_text()

    assert "TRUNCATE TABLE cdm.observation_period, cdm.person" in seed_sql
    assert seed_sql.count("),") >= 4
    assert "(2, 8532, 1975" in seed_sql
    assert "(3, 8507, 1982" in seed_sql
    assert "(4, 8507, 2001" in seed_sql
    assert "-- Expected smoke cohort count: 3" in seed_sql


def test_local_omop_cohort_sql_uses_cohort_generator_placeholders():
    cohort_sql = (HARNESS / "cohort_sql" / "born_after_1970.sql").read_text()

    assert "@target_database_schema.@target_cohort_table" in cohort_sql
    assert "@target_cohort_id" in cohort_sql
    assert "@cdm_database_schema.person" in cohort_sql
    assert "@cdm_database_schema.observation_period" in cohort_sql
    assert "p.year_of_birth >= 1970" in cohort_sql


def test_local_omop_smoke_script_documents_expected_count_and_env():
    smoke_script = (HARNESS / "smoke_federated.py").read_text()

    assert '"EXPECTED_COUNT": "3"' in smoke_script
    assert '"DATABASE_URI": "jdbc:postgresql://localhost:5433/omop"' in smoke_script
    assert '"DB_PARAM_RESULTS_SCHEMA": "results"' in smoke_script
    assert "_run_generate_cohort_count" in smoke_script
