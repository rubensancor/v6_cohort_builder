
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

The image builds on vantage6's `algorithm-ohdsi-base` (pinned by digest in the
`Dockerfile`), which carries R, Java and the OHDSI R packages with their
[`vantage6/python-ohdsi`](https://github.com/vantage6/python-ohdsi) wrappers.
`pyproject.toml` adds the `ohdsi-*` packages the base lacks and pins `rpy2` to
the versions that load against the base's R 4.2.

Running the OHDSI code outside the image needs R, Java and those R packages.
The unit tests stub the OHDSI calls and need none of them:

```bash
python -m pytest test/test_cohort_helpers.py test/test_federated.py test/test_central.py
```

### Usage

On vantage6 5 a cohort is built in one session with two steps, which the
client runs in order (`README-v5.md` explains why): `generate_cohort`, then
either `central_function` for the total or `cohort_count` for each node's
row.

1. `generate_cohort`, a data-extraction step on each node's `omop` database,
   with `cohort_name` and exactly one of `sql` (OHDSI CohortGenerator SQL) or
   `atlas_json` (an ATLAS cohort expression), plus optional `cohort_id` and
   `overwrite`. It writes the cohort to the node's results `cohort` table and
   leaves a one-row dataframe with the outcome in the session.
2. `cohort_count`, a federated step on that dataframe. It returns each node's
   row: `status`, `cohort_id`, `count`, `below_minimum`, `minimum_count` and,
   on failure, `message`. It returns nothing else, whatever dataframe it is
   given.

Nodes accept `sql` only when their administrator allows it (see below);
`atlas_json` is always accepted.

A count from 1 up to the node's minimum (5 by default) never leaves the node:
the row carries `count: null` and `below_minimum: true` instead, and the
algorithm log does not print it either. Zero is shared. Node administrators
choose their own minimum in the node configuration:

```yaml
algorithm_env:
  COHORT_BUILDER_MINIMUM_COUNT: 5
```

The `sql` input is off by default, because the requester's own SQL can make
the count reveal any value in the database (see the privacy documentation).
A node that trusts its requesters can turn it on:

```yaml
algorithm_env:
  COHORT_BUILDER_ALLOW_SQL: true
```

`central_function`, a central step run on the same dataframe, asks each
node's `cohort_count` (optionally only `organizations_to_include`) and returns
every node's row, the errors and the total: `total_count` when it is exact,
and `total_range`, the lowest and highest possible total, when some node
withheld its count.

Pass the same `cohort_id` to every node: when it is omitted, each node makes
one up from the current time. If a node already holds rows for that cohort id,
generation fails unless `overwrite` is true.

A reference client that runs both steps and adds up the counts is
`src/vantage6_cohort.py` in the PROTECT-CHILD app repository
(`pc_cohort_langgraph`); `deploy/omop/run-cohort-builder.py` there drives it
from the command line.

Each node needs an OMOP CDM database of type `omop` whose `env` block gives
`dbms`, `user`, `password`, `cdm_database`, `cdm_schema` and
`results_schema` (example in `README-v5.md`). The node hands them to the
algorithm container as `DATABASE_URI`, `DATABASE_TYPE` and `DB_PARAM_*`, and
the `@data_extraction` decorator passes them to `generate_cohort` as
`connection_details`: `uri`, `type`, `DBMS`, `USER`, `PASSWORD`,
`CDM_DATABASE`, `CDM_SCHEMA` and `RESULTS_SCHEMA`.

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
