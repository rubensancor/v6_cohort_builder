
# pc-cohort-builder

SQL or ATLAS JSON based cohort generator

This algorithm is designed to be run with the [vantage6](https://vantage6.ai)
infrastructure for distributed analysis and learning.

The base code for this algorithm has been created via the
[v6-algorithm-template](https://github.com/vantage6/v6-algorithm-template)
template generator.

### Checklist

Note that the template generator does not create a completely ready-to-use
algorithm yet. There are still a number of things you have to do yourself.
Please ensure to execute the following steps. The steps are also indicated with
TODO statements in the generated code - so you can also simply search the
code for TODO instead of following the checklist below.

- [ ] Fill out the fields in the `pyproject.toml` file, such as a URL to your code
      repository. Alternatively, remove these fields.
- [ ] Implement your algorithm functions.
  - [ ] You are free to add more arguments to the functions. Be sure to add them
    *after* the `client` and dataframe arguments.
  - [ ] When adding new arguments, update the argument values in the test scripts
    under ``test/`` (for example ``test/test_compute.py``).
  - [ ] Run local tests with MockNetwork: ``uv sync --group dev`` then
    ``uv run python test/test_compute.py`` (or the extraction/preprocessing script).
- [ ] If you are using Python packages that are not in the standard library, add
  them to the `pyproject.toml` file. Note that `pandas` is already included by default.
- [ ] Fill in the documentation template. This will help others to understand your
      algorithm, be able to use it safely, and to contribute to it.
- [ ] If you want to submit your algorithm to a vantage6 algorithm store, be sure
  to fill in everything in ``algorithm_store.json`` (and be sure to update
  it if you change function names, arguments, etc.). It is recommended to run
  ``v6 algorithm generate-store-json`` to automatically generate the file - this
  should work especially well if you have added proper docstrings to your functions.
  Note that you do need the `vantage6` CLI to be able to use this command, which can be
  installed by e.g. running `pip install vantage6` (or `uv pip install vantage6`).
- [ ] Finally, remove this checklist section to keep the README clean.

### OHDSI dependencies

The algorithm installs the Python wrappers from
[`vantage6/python-ohdsi`](https://github.com/vantage6/python-ohdsi) through the
`ohdsi-*` packages in `pyproject.toml`. These packages depend on `rpy2`, so a
working R installation must be available when installing or running the
algorithm. The Dockerfile installs R, Java, and the required OHDSI R packages.

For local development, install R first and then run:

```bash
uv sync --group dev
```

### Usage

Submit `central_function` from the vantage6 client with either CohortGenerator
SQL or an ATLAS cohort expression JSON. Provide exactly one of `sql` or
`atlas_json`.

Example central call with SQL:

```python
task = client.task.create(
    method="central_function",
    arguments={
        "cohort_name": "Adults born after 1970",
        "sql": "SELECT * FROM @cdm_database_schema.person WHERE year_of_birth >= 1970",
        "cohort_id": 1001,
        "overwrite": False,
    },
    organizations=[1],
)
result = client.wait_for_results(task_id=task["id"])
```

Example central call with ATLAS JSON:

```python
task = client.task.create(
    method="central_function",
    arguments={
        "cohort_name": "ATLAS phenotype",
        "atlas_json": atlas_expression_json,
        "overwrite": False,
    },
    organizations=[1],
)
result = client.wait_for_results(task_id=task["id"])
```

If `cohort_id` is omitted, the central function generates a positive identifier
and sends that same id to every federated node. If a node already contains rows
for that cohort id, cohort generation fails unless `overwrite` is `True`.

The central result contains each successful node's exact `count`. `total_count`
is the sum of those counts only when all expected nodes return success; if any
node returns an error or is missing, `total_count` is `null` and the failed node
details are listed in `errors`.

Each node that runs `generate_cohort_count` must be configured for an OMOP CDM
database with these environment values:

```text
DATABASE_URI=jdbc:postgresql://host:5432/omop
DATABASE_TYPE=OMOP
DB_PARAM_DBMS=postgresql
DB_PARAM_USER=...
DB_PARAM_PASSWORD=...
DB_PARAM_CDM_DATABASE=omop
DB_PARAM_CDM_SCHEMA=cdm
DB_PARAM_RESULTS_SCHEMA=results
```

### Local OMOP smoke test

The `local-omop/` directory contains a tiny PostgreSQL OMOP-like database for
testing `generate_cohort_count` against a real database. It creates a `cdm`
schema with five people and an empty `results` schema for CohortGenerator.
The included cohort SQL selects people born in or after 1970, so the expected
subject count is `3`.

Start the database:

```bash
docker compose -f local-omop/docker-compose.yml up -d
```

Run the federated smoke test from this package directory:

```bash
uv run python local-omop/smoke_federated.py
```

The script sets the local node environment variables by default:

```text
DATABASE_URI=jdbc:postgresql://localhost:5433/omop
DATABASE_TYPE=OMOP
DB_PARAM_DBMS=postgresql
DB_PARAM_USER=omop
DB_PARAM_PASSWORD=omop
DB_PARAM_CDM_DATABASE=omop
DB_PARAM_CDM_SCHEMA=cdm
DB_PARAM_RESULTS_SCHEMA=results
```

It calls `_run_generate_cohort_count` with `overwrite=True` and cohort ID
`900001`. A successful result should contain `"status": "success"` and
`"count": 3`.

You can also inspect the generated rows directly:

```bash
docker exec pc-cohort-builder-omop psql -U omop -d omop \
  -c "SELECT cohort_definition_id, COUNT(DISTINCT subject_id) AS subjects FROM results.cohort GROUP BY cohort_definition_id;"
```

Clean up the database and volume:

```bash
docker compose -f local-omop/docker-compose.yml down -v
```

This smoke test still requires the Python OHDSI wrappers, R, Java, and the
OHDSI R packages to be installed in the environment where the script is run.
If those are missing, the script will return the underlying OHDSI/R error.

### Dockerizing your algorithm

To finally run your algorithm on the vantage6 infrastructure, you need to
create a Docker image of your algorithm.

#### Manually via ``make``

You can build (and optionally push) locally:

```bash
make image
# or with push:
make image PUSH_REG=true TAG=1.0.0 VANTAGE6_VERSION=5.0.0
```

#### Manually via ``docker``

Alternatively, a Docker image can be created by executing the following command in the
root of your algorithm directory:

```bash
docker build -t [my_docker_image_name] .
```

where you should provide a sensible value for the Docker image name. The
`docker build` command will create a Docker image that contains your algorithm.
You can create an additional tag for it by running

```bash
docker tag [my_docker_image_name] [another_image_name]
```

This way, you can e.g. do
`docker tag local_average_algorithm ghcr.io/vantage6/algorithm/average` to
make the algorithm available on a remote Docker registry (in this case
`ghcr.io`).

Finally, you need to push the image to the Docker registry. This can be done
by running

```bash
docker push [my_docker_image_name]
```

Note that you need to be logged in to the Docker registry before you can push
the image. You can do this by running `docker login` and providing your
credentials. Check [this page](https://docs.docker.com/get-started/04_sharing_app/)
For more details on sharing images on Docker Hub. If you are using a different
Docker registry, check the documentation of that registry and be sure that you
have sufficient permissions.
