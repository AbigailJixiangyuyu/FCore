from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.repositories.datasets import DatasetRepository


URL = "/api/datasets/ethereum-eth/snapshots"
TRIANGLE = "\ufeffu,v\r\n001,002\r\n002,001\r\n002,003\r\n003,001\r\n004,004\r\n"


def context(catalog):
    return {key: catalog[key] for key in ("dataset_id", "dataset_version", "observed_until")}


def upload(client, page, catalog, csv, operation=None):
    return client.post(URL, headers=page, files={"file": ("graph.csv", csv, "text/csv")},
                       data={**context(catalog), "operation_id": str(operation or uuid4())})


def test_static_update_advances_current_then_history_and_isolates_pages(app_with_test_core, monkeypatch):
    base_read = DatasetRepository.read

    def observed_only(repo, dataset_id, name):
        assert name not in ("S13.csv", "S14.csv", "replay.json")
        return base_read(repo, dataset_id, name)

    monkeypatch.setattr(DatasetRepository, "read", observed_only)
    page = {"X-FCore-Session": str(uuid4())}
    with TestClient(app_with_test_core(Settings())) as client:
        original = client.get(URL).json()
        first = upload(client, page, original, TRIANGLE)
        assert first.status_code == 201, first.text
        result = first.json()
        assert (result["node_count"], result["edge_count"], result["next_snapshot_id"]) == (4, 3, "S14")
        current = context(result["dataset"])
        assert current["observed_until"] == "S13"
        frame = client.get(f"{URL}/S13", headers=page, params={"dataset_version": current["dataset_version"]}).json()
        assert frame["core_numbers"] == {"001": 2, "002": 2, "003": 2, "004": 0}
        assert frame["stats"]["transaction_count"] is None
        assert all(edge["transaction_count"] is None for edge in frame["edges"])
        for algorithm in ("tccs", "parallel", "pkmc"):
            body = {"algorithm": algorithm, **current}
            if algorithm == "pkmc":
                body.pop("observed_until")  # Omitted bounds use this page's current snapshot.
            endpoint = "/api/queries/max-core" if algorithm == "pkmc" else "/api/queries/local-core"
            if algorithm != "pkmc":
                body.update(account="001", k=2)
            response = client.post(endpoint, json=body, headers=page)
            assert response.status_code == 200, response.text
            community, = response.json()["structures"]
            assert community["members"] == ["001", "002", "003"]
            series = client.post("/api/evidence/series", headers=page, json={
                **current, "structures": [community], "metric": "transaction_count"
            }).json()["series"][0]["points"]
            assert series[-1]["value"] is None and series[-1]["status"] == "unavailable"

        anomaly = client.post("/api/anomalies/discover", json=current, headers=page).json()
        assert anomaly["status"] == "not_evaluated" and not anomaly["accounts"]
        models = client.get("/api/datasets/ethereum-eth/link-prediction/models", headers=page, params=current)
        assert models.json()["models"][0]["status"] == "not_ready"
        assert client.post("/api/link-prediction/community", headers=page, json=current).status_code == 503
        assert client.get(f"{URL}/S14", headers=page, params=current).status_code == 404

        second = upload(client, page, current, "u,v\nNew,New\n").json()
        advanced = context(second["dataset"])
        assert advanced["observed_until"] == "S14"
        catalog = client.get(URL, headers=page).json()
        assert [s["kind"] for s in catalog["snapshots"][-4:]] == ["history", "history", "present", "future"]
        new_graph = client.get(f"{URL}/S14", headers=page, params=advanced).json()
        assert new_graph["core_numbers"] == {"New": 0} and not new_graph["edges"]
        window = {"start_snapshot_id": "S13", "end_snapshot_id": "S13"}
        history = client.post("/api/patterns/mine", headers=page, json={
            **advanced, **window, "pattern": "historical_core", "k": 2
        }).json()["structures"]
        assert [row["members"] for row in history] == [["001", "002", "003"]]
        assert history[0]["metrics"]["transaction_count"] is None
        mixed = client.get("/api/datasets/ethereum-eth/aggregate", headers=page,
                           params={**advanced, **window, "start_snapshot_id": "S12"}).json()
        assert mixed["stats"]["transaction_count"] is None
        assert any(e["transaction_count"] is not None for e in mixed["edges"])
        assert upload(client, page, advanced, "u,v\n").json()["node_count"] == 0
        assert client.get(URL, headers={"X-FCore-Session": str(uuid4())}).json() == original
        assert client.delete("/api/demo-session", headers=page).status_code == 204
        assert client.get(URL, headers=page).json() == original


def test_append_validation_retry_and_simultaneous_updates(app_with_test_core):
    page = {"X-FCore-Session": str(uuid4())}
    with TestClient(app_with_test_core(Settings())) as client:
        original = client.get(URL).json()
        for csv, line in [("u,v,t\n", 1), ("u,v\na,\n", 2), ("u,v\na,b\nc,d,e", 3),
                          (b"u,v\nX,\xff", 2)]:
            invalid = upload(client, page, original, csv)
            assert invalid.status_code == 422 and f"Line {line}" in invalid.json()["detail"]
        assert client.get(URL, headers=page).json() == original
        operation = uuid4()
        with ThreadPoolExecutor(2) as pool:
            copies = list(pool.map(lambda _: upload(client, page, original, TRIANGLE, operation), range(2)))
        assert all(r.status_code == 201 for r in copies) and copies[0].json() == copies[1].json()
        assert upload(client, page, original, TRIANGLE).status_code == 409
        assert upload(client, page, original, "u,v\n", operation).status_code == 409
        current = copies[0].json()["dataset"]
        with ThreadPoolExecutor(2) as pool:
            updates = list(pool.map(lambda csv: upload(client, page, current, csv), [TRIANGLE, "u,v\n"]))
        assert sorted(r.status_code for r in updates) == [201, 409]
        assert client.get(URL, headers=page).json()["observed_until"] == "S14"
