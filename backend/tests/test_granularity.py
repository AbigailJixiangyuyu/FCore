from collections import Counter
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.repositories.granularity import view_repository
from app.services.dataset_import import import_dataset


def events(repo, manifest):
    rows = []
    for meta in manifest.snapshots[:-1]:
        start = datetime.fromisoformat(meta.starts_at).timestamp()
        end = datetime.fromisoformat(meta.ends_at).timestamp()
        frame = repo.snapshot(manifest.dataset_id, meta.snapshot_id)
        for t in frame.transactions:
            assert start <= t.t < end
            rows.append((t.u, t.v, t.t))
    return Counter(rows)


@pytest.mark.parametrize("dataset,grain,current", [
    ("email-eu-core-dept3", "weekly", "S70"), ("email-eu-core-dept3", "monthly", "S17"),
    ("ethereum-eth", "weekly", "S12"), ("ethereum-eth", "monthly", "S03"),
    ("synthetic-small", "weekly", "S01"), ("synthetic-small", "monthly", "S01"),
])
def test_repartition_preserves_events_and_cutoff(dataset, grain, current, monkeypatch):
    source = DatasetRepository(Settings().data_dir)
    _, base = source.locate(dataset)
    read = source.read
    def observed_only(dataset_id, name):
        assert name not in ("replay.json", base.snapshots[-1].snapshot_id + ".csv")
        return read(dataset_id, name)
    monkeypatch.setattr(source, "read", observed_only)
    repo = view_repository(source, dataset, grain)
    _, view = repo.locate(dataset)
    assert view.observed_until == current
    assert view.snapshots[-2].ends_at == base.snapshots[-2].ends_at
    assert view.snapshots[0].starts_at == base.snapshots[0].starts_at
    assert all(a.ends_at == b.starts_at for a, b in zip(view.snapshots, view.snapshots[1:]))
    assert events(source, base) == events(repo, view)
    assert (repo is source) == (dataset == "ethereum-eth" and grain == "weekly")


def test_week_boundary_duplicates_and_empty_history(tmp_path):
    day = 86400
    # Importer rounds the cutoff to the next whole minute after the last observation.
    cutoff = 31 * day
    edge = cutoff - 7 * day
    payload = f"u,v,t\na,b,0\na,b,{edge - 0.25}\na,b,{edge}\na,b,{edge}\na,b,{cutoff - 1}\n"
    source = DatasetRepository(tmp_path)
    base = import_dataset(tmp_path, "boundary.csv", payload.encode())
    view = view_repository(source, base.dataset_id, "weekly")
    manifest = view.manifest
    n = [len(view.snapshot(base.dataset_id, m.snapshot_id).transactions) for m in manifest.snapshots[:-1]]
    assert n == [1, 0, 0, 1, 3]
    assert datetime.fromisoformat(manifest.snapshots[-1].ends_at) - datetime.fromisoformat(manifest.snapshots[-1].starts_at) == timedelta(days=7)


def test_view_context_scopes_queries_evidence_and_models(app_with_test_core):
    with TestClient(app_with_test_core(Settings())) as client:
        path = "/api/datasets/ethereum-eth"
        monthly = client.get(path + "/snapshots?granularity=monthly").json()
        ctx = {key: monthly[key] for key in ("dataset_id", "dataset_version", "observed_until")}
        result = client.post("/api/queries/max-core", json={**ctx, "algorithm": "pkmc"}).json()["structures"][0]
        assert result["snapshot_id"] == "S03"
        series = client.post("/api/evidence/series", json={**ctx, "structures": [result]}).json()
        assert [p["snapshot_id"] for p in series["series"][0]["points"]] == ["S01", "S02", "S03"]
        other = client.get(path + "/snapshots").json()
        wrong = {key: other[key] for key in ctx}
        assert client.post("/api/evidence/series", json={**wrong, "structures": [result]}).status_code == 409
        assert client.get(path + "/snapshots/S04", params=ctx).status_code == 404
        model, = client.get(path + "/link-prediction/models", params=ctx).json()["models"]
        assert model["status"] == "not_ready" and "four historical" in model["message"]


def test_static_append_reslices_at_the_new_cutoff(app_with_test_core):
    page = {"X-FCore-Session": str(uuid4())}
    with TestClient(app_with_test_core(Settings()), headers=page) as client:
        path = "/api/datasets/email-eu-core-dept3/snapshots"
        base = next(item for item in client.get("/api/datasets").json()["datasets"]
                    if item["dataset_id"] == "email-eu-core-dept3")
        assert base["granularities"] == ["weekly", "monthly"]
        assert client.get(path, params={"granularity": "original"}).status_code == 422
        old = client.get(path, params={"granularity": "weekly"}).json()
        assert client.get(path).json() == old
        upload = client.post(path, data={"operation_id": str(uuid4()), "dataset_version": base["dataset_version"],
                                        "observed_until": base["observed_until"]},
                             files={"file": ("update.csv", b"u,v\nnew1,new2\n")})
        assert upload.status_code == 201
        view = client.get(path, params={"granularity": "weekly"}).json()
        old_cutoff = datetime.fromisoformat(old["snapshots"][-2]["ends_at"])
        assert datetime.fromisoformat(view["snapshots"][-2]["ends_at"]) == old_cutoff + timedelta(minutes=base["snapshot_minutes"])
        current_url = path + "/" + view["observed_until"]
        graph = client.get(current_url, params={"dataset_version": view["dataset_version"]}).json()
        assert [(edge["u"], edge["v"], edge["transaction_count"]) for edge in graph["edges"]] == [("new1", "new2", None)]
        assert client.get(current_url, params={"dataset_version": old["dataset_version"]}).status_code == 409
        previous = client.get(path + "/" + view["snapshots"][-3]["snapshot_id"],
                              params={"dataset_version": view["dataset_version"]}).json()
        assert not previous["edges"]
