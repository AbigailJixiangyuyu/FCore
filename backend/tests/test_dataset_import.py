from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.datasets import DatasetRepository

UPLOAD_URL = "/api/datasets/import"


def upload(client, content, name="交互样例.csv"):
    return client.post(UPLOAD_URL, files={"file": (name, content, "text/csv")})


def test_import_registers_sorted_interactions_and_preserves_the_observation_cutoff(
    tmp_path, app_with_test_core,
):
    data_dir = tmp_path / "data"
    content = (
        '\ufeffu,v,t\r\n'
        'Ab,001,1767233466.125\r\n'
        '"a,b",001,1767232800\r\n'
        '001,Ab,1767233465\r\n'
        '001,ab,1767233465\r\n'
        '001,Ab,1767233465\r\n'
    )
    with TestClient(app_with_test_core(Settings(project_root=tmp_path))) as client:
        response = upload(client, content)
        assert response.status_code == 201, response.json()
        dataset = response.json()
        assert upload(client, content).json() == dataset
        assert client.get("/api/datasets").json()["datasets"] == [dataset]
        dataset_id = dataset["dataset_id"]
        url = f"/api/datasets/{dataset_id}/snapshots"
        context = {
            "dataset_id": dataset_id,
            "dataset_version": dataset["dataset_version"],
            "observed_until": "S12",
        }
        catalog = client.get(url).json()
        assert dataset["name"] == "交互样例"
        assert dataset["timestamp_basis"] == "unix"
        assert catalog["snapshot_minutes"] == 1
        assert len(catalog["snapshots"]) == 13
        summary = client.get(f"{url}/S12", params=context).json()
        assert summary["stats"]["transaction_count"] == 4
        assert [(e["u"], e["v"], e["transaction_count"]) for e in summary["edges"]] == [
            ("001", "Ab", 3), ("001", "ab", 1),
        ]
        assert {node["id"] for node in summary["nodes"]} == {"001", "Ab", "ab"}
        assert client.get(f"{url}/S13", params=context).status_code == 404
        defaults = dataset["query_defaults"]
        query = client.post("/api/queries/local-core", json={
            **context, "account": defaults["current_account"], "k": defaults["current_k"],
        })
        assert query.status_code == 200, query.json()
        assert query.json()["structures"][0]["members"] == ["001", "Ab", "ab"]

    repository = DatasetRepository(data_dir)
    assert len(list(data_dir.iterdir())) == 1
    all_times = []
    for meta in catalog["snapshots"][:-1]:
        frame = repository.snapshot(dataset_id, meta["snapshot_id"])
        start = datetime.fromisoformat(meta["starts_at"]).timestamp()
        end = datetime.fromisoformat(meta["ends_at"]).timestamp()
        assert end - start == 60
        assert all(start <= event.t < end for event in frame.transactions)
        all_times.extend(event.t for event in frame.transactions)
    assert all_times == [
        1767232800, 1767233465, 1767233465, 1767233465, 1767233466.125,
    ]
    early = repository.snapshot(dataset_id, "S01")
    assert (early.transactions[0].u, early.transactions[0].v) == ("001", "a,b")
    current = repository.snapshot(dataset_id, "S12")
    assert [(e.u, e.v) for e in current.transactions] == [
        ("001", "Ab"), ("001", "ab"), ("001", "Ab"), ("001", "Ab"),
    ]


def test_invalid_upload_reports_a_row_and_leaves_no_partial_dataset(tmp_path):
    with TestClient(create_app(Settings(project_root=tmp_path))) as client:
        cases = [
            ("v,u,t\n", "第 1 行", "表头"),
            ("u,v,t\nu,v\n", "第 2 行", "三列"),
            ("u,v,t\nu,v,1,2\n", "第 2 行", "三列"),
            ("u,v,t\n,001,1\n", "第 2 行", "非空"),
            ("u,v,t\n001, ,1\n", "第 2 行", "非空"),
            ("u,v,t\n001,002,1\n001,002,NaN\n", "第 3 行", "非负有限"),
            ("u,v,t\n001,002,-1\n", "第 2 行", "非负有限"),
            ("u,v,t\n001,002,inf\n", "第 2 行", "非负有限"),
            ("u,v,t\n001,002,2026-01-01\n", "第 2 行", "非负有限"),
            ("u,v,t\n001,002,1767232805000\n", "第 2 行", "Unix 秒"),
            ("u,v,t", "第 2 行", "至少需要一条"),
        ]
        for content, row, reason in cases:
            response = upload(client, content)
            assert response.status_code == 422, (content, response.json())
            detail = response.json()["detail"]
            assert row in detail and reason in detail
        assert upload(client, b"u,v,t\n\xff,v,1\n").status_code == 422
        assert upload(client, "u,v,t\n001,002,1", "sample.txt").status_code == 422
        assert client.post(UPLOAD_URL, files=[
            ("file", ("one.csv", "u,v,t\nu,v,1")),
            ("file", ("two.csv", "u,v,t\nu,v,2")),
        ]).status_code == 422
        assert client.get("/api/datasets").json() == {"datasets": []}
    assert not (tmp_path / "data").exists()


def test_short_upload_keeps_the_latest_interaction_in_s12(tmp_path):
    settings = Settings(project_root=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = upload(client, "u,v,t\n001,002,0")
        assert response.status_code == 201, response.json()
        dataset = response.json()
        assert dataset["query_defaults"]["history_account"] is None
        context = {key: dataset[key] for key in ("dataset_id", "dataset_version", "observed_until")}
        response = client.post("/api/patterns/mine", json={**context, "pattern": "periodic", "account": "001", "k": 1})
        assert response.status_code == 200, response.json()
        assert response.json()["structures"] == []
    repository = DatasetRepository(settings.data_dir)
    assert not repository.snapshot(dataset["dataset_id"], "S11").transactions
    assert repository.snapshot(dataset["dataset_id"], "S12").transactions[0].t == 0
