"""
Run this script to test your preprocessing function locally (without building a
Docker image) using MockNetwork.

Run as:

    uv sync --group dev
    uv run python test/test_preprocessing.py

Requires vantage6-algorithm-tools
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

    # List mock organizations
    organizations = client.organization.list()
    print(organizations)
    org_ids = [organization["id"] for organization in organizations]

    dataframe = client.dataframe.preprocess(
        id_=network.hq.dataframes[0]["id"],
        image="ghcr.io/rubensancor/v6_cohort_builder",
        method="data_preprocessing_function",
        arguments={
            # TODO add sensible values
            "arg1": "some_value",
        },
    )
    print("dataframe:", dataframe)

    print("dataframes per node:")
    for node in network.nodes:
        print(node.dataframes)


if __name__ == "__main__":
    main()
