import importlib


central = importlib.import_module("pc-cohort-builder.central")
federated = importlib.import_module("pc-cohort-builder.federated")
package = importlib.import_module("pc-cohort-builder")


class FakeOrganizations:
    def list(self):
        return [{"id": 1}, {"id": 2}]


class FakeTasks:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return {"id": 99}


class FakeClient:
    def __init__(self, results):
        self.organization = FakeOrganizations()
        self.task = FakeTasks()
        self._results = results

    def wait_for_results(self, task_id):
        assert task_id == 99
        return self._results


def test_package_root_exposes_central_function_for_vantage6_wrapper():
    assert package.central_function is central.central_function


def test_package_root_exposes_generate_cohort_count_for_vantage6_wrapper():
    assert package.generate_cohort_count is federated.generate_cohort_count


def test_run_central_dispatches_sql_to_all_organizations():
    client = FakeClient(
        [
            {"organization_id": 1, "status": "success", "count": 4},
            {"organization_id": 2, "status": "success", "count": 6},
        ]
    )

    result = central._run_central_function(
        client,
        cohort_name="Death cohort",
        sql="select * from cohort_sql",
        atlas_json=None,
        cohort_id=55,
        overwrite=False,
    )

    assert client.task.created == [
        {
            "method": "generate_cohort_count",
            "arguments": {
                "sql": "select * from cohort_sql",
                "cohort_name": "Death cohort",
                "cohort_id": 55,
                "overwrite": False,
            },
            "organizations": [1, 2],
            "name": "Generate cohort Death cohort",
            "description": "Generate OMOP cohort 55 and return patient count",
        }
    ]
    assert result["total_count"] == 10
    assert result["errors"] == []


def test_run_central_converts_atlas_json_before_dispatch(monkeypatch):
    client = FakeClient(
        [
            {"organization_id": 1, "status": "success", "count": 3},
            {"organization_id": 2, "status": "success", "count": 5},
        ]
    )
    monkeypatch.setattr(central, "atlas_json_to_sql", lambda atlas_json: "generated sql")

    result = central._run_central_function(
        client,
        cohort_name="Atlas cohort",
        sql=None,
        atlas_json={"ConceptSets": []},
        cohort_id=77,
        overwrite=True,
    )

    assert client.task.created[0]["arguments"]["sql"] == "generated sql"
    assert client.task.created[0]["arguments"]["overwrite"] is True
    assert result["input_type"] == "atlas_json"
    assert result["total_count"] == 8


def test_run_central_returns_partial_results_with_errors():
    client = FakeClient(
        [
            {"organization_id": 1, "status": "success", "count": 4},
            {"organization_id": 2, "status": "error", "message": "conflict"},
        ]
    )

    result = central._run_central_function(
        client,
        cohort_name="Death cohort",
        sql="select * from cohort_sql",
        atlas_json=None,
        cohort_id=55,
        overwrite=False,
    )

    assert result["nodes"] == [{"organization_id": 1, "status": "success", "count": 4}]
    assert result["errors"] == [
        {"organization_id": 2, "status": "error", "message": "conflict"}
    ]
    assert result["total_count"] is None
