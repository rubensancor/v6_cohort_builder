# pc-cohort-builder on vantage6 5 — what had to change and why

Changes made on top of commit `3a34678` so the algorithm runs on vantage6 5.

## Three things kept it from working

### 1. The published image has no OHDSI R packages

`ghcr.io/rubensancor/v6_cohort_builder:latest` carries R 4 and Java 21 but not
`CohortGenerator`, `CirceR`, `DatabaseConnector` or `SqlRender`. The
`install.packages()` step in the Dockerfile failed during the upstream build
and R does not fail a build when a package fails to install, so the image was
published without them. Any call into `ohdsi.*` then dies at runtime.

The failure itself is `rJava` (a dependency of SqlRender and DatabaseConnector)
not linking:

```
/usr/bin/ld: cannot find -lpcre2-8
/usr/bin/ld: cannot find -ldeflate
/usr/bin/ld: cannot find -llzma
/usr/bin/ld: cannot find -lbz2
compilation failed for package 'rJava'
```

The image installs `r-base` but not the `-dev` headers R's own libraries need
when something links against them. Fix, in `Dockerfile`:

- install `r-base-dev libpcre2-dev libdeflate-dev liblzma-dev libbz2-dev
  zlib1g-dev libicu-dev` before `install.packages()`;
- make the R step fail the build if any package is missing afterwards;
- download the PostgreSQL JDBC driver, which `DatabaseConnector` needs at run
  time (`DATABASECONNECTOR_JAR_FOLDER`);
- install only the four packages the code imports. `FeatureExtraction` and
  `CohortDiagnostics` are listed in `pyproject.toml` but never used, and they
  roughly triple the build.

### 2. A federated task never sees the database

vantage6 5 injects `DATABASE_URI` and the `DB_PARAM_*` variables **only when a
task's action is `data_extraction`** (`container_manager.py`,
`if run_io.action == AlgorithmStepType.DATA_EXTRACTION`). `generate_cohort_count`
was decorated `@federated`, so it ran as `federated_compute` with no
credentials, and `parse_omop_config()` raised "Missing required OMOP
configuration" at every node.

Nothing inside a container can work around this: the in-container
`AlgorithmClient.task.create` hardcodes `"action": "federated_compute"`, so a
central function cannot dispatch extraction tasks either.

The fix follows the v5 session model:

| Step | Entry point | Action | Has DB | Returns to caller |
|---|---|---|---|---|
| 1 | `generate_cohort` (extract.py) | data_extraction | yes | no — leaves a one-row dataframe in the session |
| 2 | `cohort_count` (federated.py) | federated_compute | no | yes — reads the row back |

Orchestration (session, two tasks, aggregation) moves to the client. A
reference client lives in the PROTECT-CHILD app repository
(`pc_cohort_langgraph`, `src/vantage6_cohort.py`), with a stand-alone driver at
`deploy/omop/run-cohort-builder.py`.

`central_function` and `generate_cohort_count` remain importable and return a
clear error explaining the above, so an old task definition fails legibly.

### 3. `ohdsi.common` needs FeatureExtraction just to be imported

`cohort.py` used `ohdsi.common.convert_to_r` / `convert_from_r` for the two
pandas ↔ R data.frame conversions. `ohdsi.common` calls
`importr("FeatureExtraction")` at module level, so without that R package the
first sandbox run answered, at every node,

```
The R package "FeatureExtraction" is not installed.
```

FeatureExtraction is not needed to generate a cohort and drags in Andromeda
and a large native build. `rconvert.py` does the two conversions with rpy2
directly and `_load_ohdsi_modules` uses it instead; the Dockerfile now imports
the OHDSI path during the build so a missing R package fails there and not at
a node.

## Smaller things

- **Errors travel inside the row.** An extraction step that raises leaves no
  dataframe, and the caller only learns "crashed". `generate_cohort` therefore
  reports `status: error` plus the message in the row instead.
- **JDBC URIs are completed.** Node configurations tend to say
  `jdbc:postgresql://host`; DatabaseConnector wants host, port and database.
  `normalize_jdbc_uri` fills in `5432` and the CDM database name when absent.
- **Tests** in `test/test_federated.py` were rewritten for the new entry
  points. They stub the OHDSI calls, so they need neither R nor a database:
  `python -m pytest test/test_cohort_helpers.py test/test_federated.py test/test_central.py`.

## Node configuration this expects

```yaml
node:
  databases:
    serviceBased:
      - name: omop
        uri: jdbc:postgresql://omop-postgres.omop.svc.cluster.local
        type: omop
        env:
          user: omop_admin
          password: ...
          dbms: postgresql
          cdm_database: omop_cdm
          cdm_schema: cdm
          results_schema: results
```

Plus an egress network policy letting algorithm pods reach the database
(`task-egress-omop.yaml` in the same app repository): vantage6 isolates them with deny-all by
default, DNS included.
