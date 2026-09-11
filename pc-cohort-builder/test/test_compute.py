"""
Run this script to test your compute functions locally (without building a Docker
image) using MockNetwork.

Run as:

    uv sync --group dev
    uv run python test/test_compute.py

Requires vantage6-algorithm-tools.
"""
import pandas as pd
from pathlib import Path

from vantage6.algorithm.mock.network import MockNetwork

current_path = Path(__file__).parent


def main():
    # The MockNetwork expects a list of datasets. In this instance we are not interested in
    # extracting the data from its source. Therefore, we supply the data as a Pandas
    # dataframe avoiding the need to extract the data first
    data = pd.read_csv(current_path / "test_data.csv")
    database_label = "Database 1"

    network = MockNetwork(
        datasets=[
            {database_label: {"database": data}},
            {database_label: {"database": data}},
            {database_label: {"database": data}},
        ],
        module_name="pc-cohort-builder",
    )

    # Once the network is created, we can get the client to interact with the MockNetwork.
    client = network.user_client

    databases = [
        {"type": "dataframe", "dataframe_id": network.hq.dataframes[0]["id"]}
    ]

    organizations = client.organization.list()
    print(organizations)
    org_ids = [organization["id"] for organization in organizations]

    # Run the central method on 1 node and get the results
    central_task = client.task.create(
        method="central_function",
        arguments={
            "cohort_name": "Example cohort",
            "sql": "SELECT * FROM @cdm_database_schema.person WHERE year_of_birth >= 1970",
            "cohort_id": 1001,
            "overwrite": False,
        },
        organizations=[org_ids[0]],
        databases=databases,
    )
    results = client.wait_for_results(central_task.get("id"))
    print(results)

    # Run the federated method for all organizations. The real OHDSI path requires
    # OMOP-style node database configuration rather than a dataframe dataset.
    task = client.task.create(
        method="generate_cohort_count",
        arguments={
            "cohort_name": "Example cohort",
            "sql": "SELECT * FROM @cdm_database_schema.person WHERE year_of_birth >= 1970",
            "cohort_id": 1001,
            "overwrite": False,
        },
        organizations=org_ids,
        databases=databases,
    )
    print(task)

    # Get the results from the task
    results = client.wait_for_results(task.get("id"))
    print(results)


if __name__ == "__main__":
    main()
